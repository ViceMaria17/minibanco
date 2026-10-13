"""
Confirmação com PIN: a segunda autenticação, obrigatória antes de movimentar dinheiro.
"""
from datetime import timedelta
from decimal import Decimal

import pytest

from app import relogio
from tests.api.ajudantes import CONTAS, PINS, confirmar, iniciar, saldo

pytestmark = pytest.mark.api


@pytest.fixture
def transferencia_pendente(cliente, sessao_ana):
    """DADO que a Ana iniciou uma transferência de 1 000,00 MZN para o Bruno, ainda por confirmar."""
    resposta = iniciar(cliente, sessao_ana, "transferencia", conta_destino=CONTAS["bruno"], valor="1000")
    assert resposta.status_code == 201
    return resposta.json()["operacao_id"]


def test_pin_correcto_executa_a_operacao(cliente, sessao_ana, transferencia_pendente):
    resposta = confirmar(cliente, sessao_ana, transferencia_pendente, PINS["ana"])
    assert resposta.status_code == 200
    assert resposta.json()["comprovativo"].startswith("TRF-")
    assert saldo(cliente, sessao_ana) == Decimal("49000.00")


def test_pin_errado_nao_movimenta_dinheiro(cliente, sessao_ana, transferencia_pendente):
    resposta = confirmar(cliente, sessao_ana, transferencia_pendente, "0000")
    assert resposta.status_code == 403
    assert resposta.json()["detail"] == "PIN incorrecto. Restam 2 tentativas."
    assert saldo(cliente, sessao_ana) == Decimal("50000.00")


def test_depois_de_um_pin_errado_ainda_se_pode_confirmar(cliente, sessao_ana, transferencia_pendente):
    confirmar(cliente, sessao_ana, transferencia_pendente, "0000")
    assert confirmar(cliente, sessao_ana, transferencia_pendente, PINS["ana"]).status_code == 200


def test_tres_pins_errados_bloqueiam_a_conta(cliente, sessao_ana, transferencia_pendente):
    assert confirmar(cliente, sessao_ana, transferencia_pendente, "0000").json()["detail"].endswith("Restam 2 tentativas.")
    assert confirmar(cliente, sessao_ana, transferencia_pendente, "0000").json()["detail"].endswith("Resta 1 tentativa.")
    assert confirmar(cliente, sessao_ana, transferencia_pendente, "0000").status_code == 423
    # ENTÃO a sessão deixa de dar acesso e o login também fica bloqueado
    assert cliente.get("/api/conta", headers=sessao_ana).status_code == 423
    login = cliente.post("/api/auth/token", data={"username": "ana", "password": "Ana@2026"})
    assert login.status_code == 423


def test_pin_com_formato_invalido_e_recusado(cliente, sessao_ana, transferencia_pendente):
    resposta = confirmar(cliente, sessao_ana, transferencia_pendente, "12a4")
    assert resposta.status_code == 422
    assert "«PIN»" in resposta.json()["detail"]


def test_confirmacao_nao_pode_ser_repetida(cliente, sessao_ana, transferencia_pendente):
    # Ataque de repetição ("replay"): reenviar o mesmo pedido para transferir duas vezes
    assert confirmar(cliente, sessao_ana, transferencia_pendente, PINS["ana"]).status_code == 200
    assert confirmar(cliente, sessao_ana, transferencia_pendente, PINS["ana"]).status_code == 404
    assert saldo(cliente, sessao_ana) == Decimal("49000.00")   # debitado uma única vez


def test_outro_utilizador_nao_pode_confirmar_operacao_alheia(cliente, sessao_ana, sessao_bruno, transferencia_pendente):
    # O Bruno descobre o identificador da operação da Ana e tenta confirmá-la com o PIN dele
    resposta = confirmar(cliente, sessao_bruno, transferencia_pendente, PINS["bruno"])
    # ENTÃO a API responde como se a operação não existisse
    assert resposta.status_code == 404
    assert saldo(cliente, sessao_ana) == Decimal("50000.00")
    # E a operação continua válida para a Ana
    assert confirmar(cliente, sessao_ana, transferencia_pendente, PINS["ana"]).status_code == 200


def test_outro_utilizador_nao_pode_cancelar_operacao_alheia(cliente, sessao_ana, sessao_bruno, transferencia_pendente):
    assert cliente.delete(f"/api/operacoes/{transferencia_pendente}", headers=sessao_bruno).status_code == 404
    assert confirmar(cliente, sessao_ana, transferencia_pendente, PINS["ana"]).status_code == 200


def test_operacao_cancelada_nao_pode_ser_confirmada(cliente, sessao_ana, transferencia_pendente):
    assert cliente.delete(f"/api/operacoes/{transferencia_pendente}", headers=sessao_ana).status_code == 204
    assert confirmar(cliente, sessao_ana, transferencia_pendente, PINS["ana"]).status_code == 404
    assert saldo(cliente, sessao_ana) == Decimal("50000.00")


def test_operacao_expira_ao_fim_de_2_minutos(cliente, sessao_ana, transferencia_pendente, monkeypatch):
    # QUANDO passam 2 minutos e 1 segundo sem confirmar
    futuro = relogio.agora() + timedelta(seconds=121)
    monkeypatch.setattr(relogio, "agora", lambda: futuro)
    resposta = confirmar(cliente, sessao_ana, transferencia_pendente, PINS["ana"])
    # ENTÃO a operação já não pode ser confirmada
    assert resposta.status_code == 410
    assert saldo(cliente, sessao_ana) == Decimal("50000.00")


def test_saldo_e_verificado_de_novo_na_confirmacao(cliente, sessao_bruno):
    # DADO que o Bruno (1 500,00 MZN) inicia duas transferências de 1 000,00 MZN:
    # cada uma, sozinha, cabe no saldo; as duas juntas não.
    primeira = iniciar(cliente, sessao_bruno, "transferencia", conta_destino=CONTAS["ana"], valor="1000")
    segunda = iniciar(cliente, sessao_bruno, "transferencia", conta_destino=CONTAS["ana"], valor="1000")
    assert primeira.status_code == segunda.status_code == 201
    # QUANDO confirma as duas
    assert confirmar(cliente, sessao_bruno, primeira.json()["operacao_id"], PINS["bruno"]).status_code == 200
    resposta = confirmar(cliente, sessao_bruno, segunda.json()["operacao_id"], PINS["bruno"])
    # ENTÃO a segunda é recusada, porque o saldo já não chega
    assert resposta.status_code == 422
    assert resposta.json()["detail"] == "Saldo insuficiente para esta operação."
    assert saldo(cliente, sessao_bruno) == Decimal("500.00")
