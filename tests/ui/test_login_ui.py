"""
Interface: login, sessão e logout.
"""
from decimal import Decimal

import pytest

from tests.ui.paginas.conta import PaginaConta
from tests.ui.paginas.login import PaginaLogin

pytestmark = pytest.mark.ui


def test_login_valido_mostra_a_conta(pagina_login, driver, url_base):
    # QUANDO a Ana entra com credenciais válidas
    pagina_login.entrar("ana", "Ana@2026")
    # ENTÃO vê a página da conta, com o seu nome e o saldo
    conta = PaginaConta(driver, url_base).esperar_carregamento()
    assert conta.caminho_e("/conta")
    assert conta.nome_titular() == "Ana Machava"
    assert conta.saldo() == Decimal("50000.00")


def test_senha_errada_mostra_erro_e_fica_no_login(pagina_login):
    pagina_login.entrar("ana", "errada")
    assert pagina_login.mensagem_erro() == "Utilizador ou senha inválidos."
    assert pagina_login.esta_na_pagina()


def test_campos_vazios_mostram_aviso(pagina_login):
    pagina_login.entrar("", "")
    assert pagina_login.mensagem_erro() == "Indique o utilizador e a senha."


def test_terceira_senha_errada_bloqueia_a_conta(pagina_login):
    for senha in ("errada1", "errada2", "errada3"):
        pagina_login.entrar("ana", senha)
    assert pagina_login.esperar_texto(PaginaLogin.MENSAGEM_ERRO, "bloqueada")


def test_abrir_a_conta_sem_sessao_leva_ao_login(driver, url_base):
    # QUANDO alguém abre /conta directamente, sem ter iniciado sessão
    PaginaConta(driver, url_base).abrir()
    # ENTÃO é enviado para o login, com o motivo indicado
    login = PaginaLogin(driver, url_base)
    assert login.esta_na_pagina()
    assert "sessão expirou" in login.mensagem_info()


def test_sair_termina_a_sessao(conta_ana, driver, url_base):
    conta_ana.sair()
    login = PaginaLogin(driver, url_base)
    assert login.esta_na_pagina()
    assert login.mensagem_info() == "Sessão terminada."
    # E voltar a abrir /conta já não dá acesso
    PaginaConta(driver, url_base).abrir()
    assert login.esta_na_pagina()


def test_token_adulterado_no_navegador_termina_a_sessao(conta_ana, driver, url_base):
    # Simula um token alterado: escreve-se outro valor no sessionStorage com JavaScript
    driver.execute_script("sessionStorage.setItem('minibanco.token', 'token.adulterado.invalido')")
    driver.refresh()
    # ENTÃO a API recusa-o (401) e a página volta ao login
    login = PaginaLogin(driver, url_base)
    assert login.esta_na_pagina()
    assert "sessão expirou" in login.mensagem_info()
