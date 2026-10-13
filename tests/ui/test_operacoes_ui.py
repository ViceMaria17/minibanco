"""
Interface: operações com confirmação por PIN.
"""
import re
from decimal import Decimal

import pytest
from selenium.common.exceptions import NoAlertPresentException

pytestmark = pytest.mark.ui

CONTA_ANA = "100200300"
CONTA_BRUNO = "100200301"


def test_transferencia_confirmada_actualiza_saldo_e_movimentos(conta_ana):
    # QUANDO a Ana transfere 250,50 MZN para o Bruno
    conta_ana.transferir(CONTA_BRUNO, "250,50", "Renda de Outubro")
    # ENTÃO, antes de pedir o PIN, a confirmação mostra o resumo da operação
    resumo = conta_ana.resumo()
    assert resumo["Para"] == "100200301 (Bruno S.)"
    assert resumo["Valor"] == "250,50 MZN"
    # QUANDO confirma com o PIN correcto
    conta_ana.confirmar_com_pin("1234")
    # ENTÃO vê a mensagem de sucesso, o saldo actualizado e o novo movimento
    assert conta_ana.mensagem_sucesso().startswith("Transferência efectuada.")
    assert conta_ana.saldo() == Decimal("49749.50")
    ultimo = conta_ana.movimentos()[0]
    assert ultimo["valor"] == Decimal("-250.50")
    assert "Renda de Outubro" in ultimo["descricao"]


def test_saldo_insuficiente_mostra_erro_sem_pedir_pin(conta_bruno):
    # DADO que o Bruno tem 1 500,00 MZN
    conta_bruno.transferir(CONTA_ANA, "5000")
    assert conta_bruno.mensagem_erro() == "Saldo insuficiente para esta operação."
    assert not conta_bruno.confirmacao_aberta()
    assert conta_bruno.saldo() == Decimal("1500.00")


def test_pin_errado_mostra_erro_e_nao_movimenta_dinheiro(conta_ana):
    conta_ana.transferir(CONTA_BRUNO, "100")
    conta_ana.confirmar_com_pin("9999")
    assert conta_ana.erro_pin() == "PIN incorrecto. Restam 2 tentativas."
    assert conta_ana.confirmacao_aberta()   # pode tentar de novo
    conta_ana.cancelar_confirmacao()
    # O saldo confirma-se depois de recarregar: assim vem do servidor e não só do ecrã
    assert conta_ana.recarregar().saldo() == Decimal("50000.00")


def test_cancelar_a_confirmacao_nao_movimenta_dinheiro(conta_ana):
    conta_ana.transferir(CONTA_BRUNO, "100")
    conta_ana.cancelar_confirmacao()
    assert conta_ana.mensagem_info() == "Operação cancelada. Nenhum valor foi movimentado."
    assert conta_ana.recarregar().saldo() == Decimal("50000.00")


def test_levantamento_mostra_codigo_de_6_digitos(conta_ana):
    conta_ana.levantar("1000")
    conta_ana.confirmar_com_pin("1234")
    assert re.search(r"Código de levantamento: \d{6}\.", conta_ana.mensagem_sucesso())
    assert conta_ana.saldo() == Decimal("49000.00")


def test_descricao_com_html_e_mostrada_como_texto(conta_ana, driver):
    # Tentativa de XSS: se este texto fosse interpretado como HTML, abriria um alerta
    ataque = "<img src=x onerror=alert(1)>"
    conta_ana.transferir(CONTA_BRUNO, "10", ataque)
    conta_ana.confirmar_com_pin("1234")
    conta_ana.mensagem_sucesso()
    # ENTÃO o texto aparece tal e qual, como texto
    assert ataque in conta_ana.movimentos()[0]["descricao"]
    # E nenhum alerta foi aberto
    with pytest.raises(NoAlertPresentException):
        driver.switch_to.alert
