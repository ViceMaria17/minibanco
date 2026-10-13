"""
Regras de negócio das operações: transferência, levantamento e pagamento.

Cada operação tem DUAS fases:
  1. Iniciar   -> valida os dados e o saldo e cria uma operação PENDENTE.
                  Nesta fase nenhum valor é movimentado.
  2. Confirmar -> o utilizador volta a autenticar-se com o PIN; o saldo é verificado
                  outra vez e só então a operação é executada.
"""
import secrets
import uuid
from datetime import timedelta

from fastapi import HTTPException

from app import config, relogio
from app.dados import ENTIDADES, Conta, Movimento, OperacaoPendente, bd
from app.dinheiro import formatar, para_centavos, para_texto
from app.modelos import PedidoLevantamento, PedidoPagamento, PedidoTransferencia
from app.seguranca import verificar_pin


def erro_regra(mensagem: str) -> HTTPException:
    """Pedido bem formado, mas que viola uma regra de negócio (ex.: saldo insuficiente)."""
    return HTTPException(status_code=422, detail=mensagem)


def nao_encontrada() -> HTTPException:
    return HTTPException(status_code=404, detail="Operação não encontrada.")


def exigir_saldo(conta: Conta, valor: int) -> None:
    if valor > conta.saldo:
        raise erro_regra("Saldo insuficiente para esta operação.")


def abreviar(nome: str) -> str:
    """'Bruno Sitoe' -> 'Bruno S.'  (mostra só o necessário para confirmar o destinatário)"""
    partes = nome.split()
    return f"{partes[0]} {partes[-1][0]}." if len(partes) > 1 else partes[0]


# ---------- Fase 1: iniciar ----------

def _criar_pendente(conta: Conta, tipo: str, valor: int, detalhes: dict, resumo: list) -> dict:
    operacao = OperacaoPendente(
        id=uuid.uuid4().hex,              # identificador aleatório: impossível de adivinhar
        utilizador=conta.utilizador,
        tipo=tipo,
        valor=valor,
        detalhes=detalhes,
        expira_em=relogio.agora() + timedelta(seconds=config.SEGUNDOS_CONFIRMACAO),
    )
    with bd.trinco:
        bd.operacoes[operacao.id] = operacao
    return {
        "operacao_id": operacao.id,
        "resumo": [{"rotulo": rotulo, "valor": valor} for rotulo, valor in resumo],
        "expira_em_segundos": config.SEGUNDOS_CONFIRMACAO,
    }


def iniciar_transferencia(conta: Conta, pedido: PedidoTransferencia) -> dict:
    valor = para_centavos(pedido.valor)
    destino = bd.conta_por_numero(pedido.conta_destino)
    if destino is None:
        raise erro_regra("A conta de destino não existe.")
    if destino.numero == conta.numero:
        raise erro_regra("Não é possível transferir para a própria conta.")
    exigir_saldo(conta, valor)
    resumo = [
        ("Operação", "Transferência"),
        ("Para", f"{destino.numero} ({abreviar(destino.titular)})"),
        ("Valor", formatar(valor)),
    ]
    if pedido.descricao:
        resumo.append(("Descrição", pedido.descricao))
    detalhes = {"conta_destino": destino.numero, "descricao": pedido.descricao}
    return _criar_pendente(conta, "transferencia", valor, detalhes, resumo)


def iniciar_levantamento(conta: Conta, pedido: PedidoLevantamento) -> dict:
    valor = para_centavos(pedido.valor)
    if valor % config.LEVANTAMENTO_MULTIPLO != 0:
        raise erro_regra(f"O levantamento tem de ser múltiplo de {formatar(config.LEVANTAMENTO_MULTIPLO)}.")
    if valor > config.LEVANTAMENTO_MAXIMO:
        raise erro_regra(f"O valor máximo por levantamento é {formatar(config.LEVANTAMENTO_MAXIMO)}.")
    exigir_saldo(conta, valor)
    resumo = [("Operação", "Levantamento"), ("Valor", formatar(valor))]
    return _criar_pendente(conta, "levantamento", valor, {}, resumo)


def iniciar_pagamento(conta: Conta, pedido: PedidoPagamento) -> dict:
    valor = para_centavos(pedido.valor)
    entidade = ENTIDADES.get(pedido.entidade)
    if entidade is None:
        raise erro_regra("A entidade de pagamento não existe.")
    exigir_saldo(conta, valor)
    resumo = [
        ("Operação", "Pagamento"),
        ("Entidade", f"{entidade} ({pedido.entidade})"),
        ("Referência", pedido.referencia),
        ("Valor", formatar(valor)),
    ]
    detalhes = {"entidade": pedido.entidade, "referencia": pedido.referencia}
    return _criar_pendente(conta, "pagamento", valor, detalhes, resumo)


# ---------- Fase 2: confirmar (ou cancelar) ----------

def _obter_pendente(conta: Conta, operacao_id: str) -> OperacaoPendente:
    with bd.trinco:
        operacao = bd.operacoes.get(operacao_id)
        # Se a operação for de outra pessoa, responde-se como se não existisse:
        # assim não se revela que aquele identificador é válido.
        if operacao is None or operacao.utilizador != conta.utilizador:
            raise nao_encontrada()
        if relogio.agora() >= operacao.expira_em:
            del bd.operacoes[operacao_id]
            raise HTTPException(status_code=410, detail="O tempo para confirmar terminou. Inicie a operação novamente.")
        return operacao


def confirmar(conta: Conta, operacao_id: str, pin: str) -> dict:
    operacao = _obter_pendente(conta, operacao_id)
    verificar_pin(conta, pin)                         # 403 se estiver errado; 423 à terceira falha
    with bd.trinco:
        # A operação sai da lista ANTES de ser executada: não pode ser confirmada duas vezes
        if bd.operacoes.pop(operacao.id, None) is None:
            raise nao_encontrada()
        # O saldo pode ter mudado desde a fase 1 (ex.: outra operação entretanto confirmada)
        exigir_saldo(conta, operacao.valor)
        resultado = _EXECUTORES[operacao.tipo](conta, operacao)
        resultado["saldo"] = para_texto(conta.saldo)
        return resultado


def cancelar(conta: Conta, operacao_id: str) -> None:
    with bd.trinco:
        operacao = bd.operacoes.get(operacao_id)
        if operacao is None or operacao.utilizador != conta.utilizador:
            raise nao_encontrada()
        del bd.operacoes[operacao_id]


# ---------- Execução ----------

def _movimentar(conta: Conta, valor: int, descricao: str) -> None:
    """Altera o saldo e regista o movimento. valor > 0 é um crédito; valor < 0 é um débito."""
    conta.saldo += valor
    conta.movimentos.append(Movimento(relogio.agora(), descricao, valor, conta.saldo))


def _comprovativo(prefixo: str) -> str:
    return f"{prefixo}-{secrets.token_hex(4).upper()}"


def _executar_transferencia(conta: Conta, operacao: OperacaoPendente) -> dict:
    destino = bd.conta_por_numero(operacao.detalhes["conta_destino"])
    nota = f" — {operacao.detalhes['descricao']}" if operacao.detalhes["descricao"] else ""
    _movimentar(conta, -operacao.valor, f"Transferência para {destino.numero}{nota}")
    _movimentar(destino, operacao.valor, f"Transferência de {conta.numero}{nota}")
    return {"mensagem": "Transferência efectuada.", "comprovativo": _comprovativo("TRF")}


def _executar_levantamento(conta: Conta, operacao: OperacaoPendente) -> dict:
    # O código funciona como um segredo (permite levantar o dinheiro), por isso é
    # mostrado uma única vez e NÃO fica guardado no histórico de movimentos.
    codigo = f"{secrets.randbelow(1_000_000):06d}"
    _movimentar(conta, -operacao.valor, "Levantamento")
    return {"mensagem": "Levantamento autorizado. Use o código num ATM ou agente.", "codigo_levantamento": codigo}


def _executar_pagamento(conta: Conta, operacao: OperacaoPendente) -> dict:
    entidade = ENTIDADES[operacao.detalhes["entidade"]]
    _movimentar(conta, -operacao.valor, f"Pagamento a {entidade} — ref. {operacao.detalhes['referencia']}")
    return {"mensagem": "Pagamento efectuado.", "comprovativo": _comprovativo("PAG")}


_EXECUTORES = {
    "transferencia": _executar_transferencia,
    "levantamento": _executar_levantamento,
    "pagamento": _executar_pagamento,
}
