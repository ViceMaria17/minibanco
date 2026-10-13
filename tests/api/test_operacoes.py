"""
Operações: consulta de saldo, regras de negócio e consistência dos movimentos.
"""
from decimal import Decimal

import pytest

from tests.api.ajudantes import CONTAS, PINS, executar, iniciar, saldo

pytestmark = pytest.mark.api


def test_consulta_de_saldo(cliente, sessao_ana):
    resposta = cliente.get("/api/conta", headers=sessao_ana)
    assert resposta.status_code == 200
    assert resposta.json() == {
        "titular": "Ana Machava",
        "numero_conta": "100200300",
        "saldo": "50000.00",
        "moeda": "MZN",
    }


def test_transferencia_debita_a_origem_e_credita_o_destino(cliente, sessao_ana, sessao_bruno):
    resposta = executar(cliente, sessao_ana, "transferencia", PINS["ana"],
                        conta_destino=CONTAS["bruno"], valor="250.50", descricao="Renda")
    assert resposta.status_code == 200
    assert resposta.json()["saldo"] == "49749.50"
    assert saldo(cliente, sessao_ana) == Decimal("49749.50")
    assert saldo(cliente, sessao_bruno) == Decimal("1750.50")


def test_transferencia_fica_registada_nos_dois_extractos(cliente, sessao_ana, sessao_bruno):
    executar(cliente, sessao_ana, "transferencia", PINS["ana"],
             conta_destino=CONTAS["bruno"], valor="250.50", descricao="Renda")
    movimento_ana = cliente.get("/api/conta/movimentos", headers=sessao_ana).json()[0]
    movimento_bruno = cliente.get("/api/conta/movimentos", headers=sessao_bruno).json()[0]
    assert movimento_ana["valor"] == "-250.50"
    assert movimento_ana["saldo_apos"] == "49749.50"
    assert "Renda" in movimento_ana["descricao"]
    assert movimento_bruno["valor"] == "250.50"
    assert movimento_bruno["saldo_apos"] == "1750.50"


def test_iniciar_sem_confirmar_nao_movimenta_dinheiro(cliente, sessao_ana):
    resposta = iniciar(cliente, sessao_ana, "transferencia", conta_destino=CONTAS["bruno"], valor="1000")
    assert resposta.status_code == 201
    assert saldo(cliente, sessao_ana) == Decimal("50000.00")


@pytest.mark.parametrize("operacao, dados", [
    ("transferencia", {"conta_destino": CONTAS["ana"], "valor": "1500.01"}),
    ("levantamento", {"valor": "1600"}),
    ("pagamento", {"entidade": "10001", "referencia": "123456789", "valor": "1500.01"}),
])
def test_saldo_insuficiente_e_recusado(cliente, sessao_bruno, operacao, dados):
    # DADO que o Bruno tem 1 500,00 MZN
    resposta = iniciar(cliente, sessao_bruno, operacao, **dados)
    assert resposta.status_code == 422
    assert resposta.json()["detail"] == "Saldo insuficiente para esta operação."
    assert saldo(cliente, sessao_bruno) == Decimal("1500.00")


def test_e_possivel_usar_o_saldo_todo(cliente, sessao_bruno):
    # Valor-limite: exactamente igual ao saldo
    resposta = executar(cliente, sessao_bruno, "transferencia", PINS["bruno"],
                        conta_destino=CONTAS["ana"], valor="1500.00")
    assert resposta.status_code == 200
    assert saldo(cliente, sessao_bruno) == Decimal("0.00")


@pytest.mark.parametrize("valor", ["0", "-10", "10.001", "abc", "NaN", ""],
                         ids=["zero", "negativo", "3-casas-decimais", "texto", "nan", "vazio"])
def test_valores_invalidos_sao_recusados(cliente, sessao_ana, valor):
    resposta = iniciar(cliente, sessao_ana, "transferencia", conta_destino=CONTAS["bruno"], valor=valor)
    assert resposta.status_code == 422
    assert "«valor»" in resposta.json()["detail"]
    assert saldo(cliente, sessao_ana) == Decimal("50000.00")


def test_nao_e_possivel_transferir_para_a_propria_conta(cliente, sessao_ana):
    resposta = iniciar(cliente, sessao_ana, "transferencia", conta_destino=CONTAS["ana"], valor="10")
    assert resposta.status_code == 422
    assert resposta.json()["detail"] == "Não é possível transferir para a própria conta."


def test_conta_de_destino_inexistente(cliente, sessao_ana):
    resposta = iniciar(cliente, sessao_ana, "transferencia", conta_destino="999999999", valor="10")
    assert resposta.status_code == 422
    assert resposta.json()["detail"] == "A conta de destino não existe."


@pytest.mark.parametrize("valor", ["100", "19900", "20000"])
def test_levantamentos_dentro_das_regras_sao_aceites(cliente, sessao_ana, valor):
    assert iniciar(cliente, sessao_ana, "levantamento", valor=valor).status_code == 201


@pytest.mark.parametrize("valor, motivo", [
    ("150", "múltiplo"),
    ("20000.50", "múltiplo"),
    ("20100", "máximo"),
])
def test_levantamentos_fora_das_regras_sao_recusados(cliente, sessao_ana, valor, motivo):
    resposta = iniciar(cliente, sessao_ana, "levantamento", valor=valor)
    assert resposta.status_code == 422
    assert motivo in resposta.json()["detail"]


def test_levantamento_devolve_codigo_que_nao_fica_no_historico(cliente, sessao_ana):
    resposta = executar(cliente, sessao_ana, "levantamento", PINS["ana"], valor="500")
    codigo = resposta.json()["codigo_levantamento"]
    assert len(codigo) == 6 and codigo.isdigit()
    # O código é um segredo: aparece uma única vez e não fica guardado nos movimentos
    movimentos = cliente.get("/api/conta/movimentos", headers=sessao_ana).json()
    assert all(codigo not in movimento["descricao"] for movimento in movimentos)


def test_pagamento_valido(cliente, sessao_ana):
    resposta = executar(cliente, sessao_ana, "pagamento", PINS["ana"],
                        entidade="10001", referencia="123456789", valor="1250")
    assert resposta.status_code == 200
    assert resposta.json()["comprovativo"].startswith("PAG-")
    assert saldo(cliente, sessao_ana) == Decimal("48750.00")


def test_pagamento_a_entidade_inexistente(cliente, sessao_ana):
    resposta = iniciar(cliente, sessao_ana, "pagamento", entidade="99999", referencia="123456789", valor="10")
    assert resposta.status_code == 422
    assert resposta.json()["detail"] == "A entidade de pagamento não existe."


@pytest.mark.parametrize("referencia", ["12345678", "1234567890", "12345678A"])
def test_pagamento_com_referencia_invalida(cliente, sessao_ana, referencia):
    resposta = iniciar(cliente, sessao_ana, "pagamento", entidade="10001", referencia=referencia, valor="10")
    assert resposta.status_code == 422
    assert "«referência»" in resposta.json()["detail"]
