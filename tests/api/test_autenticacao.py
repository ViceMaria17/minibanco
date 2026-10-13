"""
Autenticação: login OAuth2, bloqueio por tentativas falhadas e logout.
"""
from datetime import timedelta

import jwt
import pytest

from app import relogio
from tests.api.ajudantes import cabecalho, iniciar_sessao

pytestmark = pytest.mark.api


def login(cliente, utilizador, senha):
    return cliente.post("/api/auth/token", data={"username": utilizador, "password": senha})


def test_login_valido_devolve_token_bearer(cliente):
    # QUANDO a Ana se autentica com credenciais válidas
    resposta = login(cliente, "ana", "Ana@2026")
    # ENTÃO recebe um token do tipo "bearer", válido durante 15 minutos
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["token_type"] == "bearer"
    assert corpo["expires_in"] == 15 * 60
    assert corpo["access_token"].count(".") == 2   # um JWT tem 3 partes: cabeçalho.conteúdo.assinatura


def test_senha_errada_devolve_401_com_cabecalho_bearer(cliente):
    resposta = login(cliente, "ana", "errada")
    assert resposta.status_code == 401
    assert resposta.json()["detail"] == "Utilizador ou senha inválidos."
    assert resposta.headers["WWW-Authenticate"] == "Bearer"


def test_utilizador_inexistente_tem_a_mesma_resposta_que_senha_errada(cliente):
    # Se as respostas fossem diferentes, um atacante descobriria quem tem conta
    senha_errada = login(cliente, "ana", "errada")
    inexistente = login(cliente, "naoexiste", "errada")
    assert inexistente.status_code == senha_errada.status_code
    assert inexistente.json() == senha_errada.json()


def test_tres_senhas_erradas_bloqueiam_a_conta(cliente):
    assert login(cliente, "ana", "errada1").status_code == 401
    assert login(cliente, "ana", "errada2").status_code == 401
    assert login(cliente, "ana", "errada3").status_code == 423
    # ENTÃO nem a senha certa funciona enquanto o bloqueio durar
    assert login(cliente, "ana", "Ana@2026").status_code == 423


def test_bloqueio_termina_ao_fim_de_5_minutos(cliente, monkeypatch):
    # DADO que a conta da Ana foi bloqueada
    for _ in range(3):
        login(cliente, "ana", "errada")
    # QUANDO passam 5 minutos e 1 segundo (o relógio da aplicação é substituído)
    futuro = relogio.agora() + timedelta(minutes=5, seconds=1)
    monkeypatch.setattr(relogio, "agora", lambda: futuro)
    # ENTÃO o login volta a funcionar
    assert login(cliente, "ana", "Ana@2026").status_code == 200


def test_login_certo_reinicia_o_contador_de_falhas(cliente):
    for _ in range(2):
        login(cliente, "ana", "errada")
    assert login(cliente, "ana", "Ana@2026").status_code == 200
    # Depois de um login certo, voltam a ser precisas 3 falhas para bloquear
    assert login(cliente, "ana", "errada").status_code == 401
    assert login(cliente, "ana", "errada").status_code == 401


def test_token_nao_contem_a_senha(cliente):
    token = iniciar_sessao(cliente, "ana")
    # O conteúdo de um JWT lê-se sem a chave: por isso nunca se põem segredos lá dentro
    conteudo = jwt.decode(token, options={"verify_signature": False})
    assert conteudo["sub"] == "ana"
    assert "Ana@2026" not in str(conteudo)


def test_logout_revoga_o_token(cliente):
    cabecalhos = cabecalho(iniciar_sessao(cliente, "ana"))
    assert cliente.get("/api/conta", headers=cabecalhos).status_code == 200
    assert cliente.post("/api/auth/logout", headers=cabecalhos).status_code == 204
    # ENTÃO o mesmo token deixa de ser aceite, mesmo ainda não tendo expirado
    assert cliente.get("/api/conta", headers=cabecalhos).status_code == 401
