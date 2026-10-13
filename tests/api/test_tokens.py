"""
Autorização: só pedidos com um token JWT válido chegam aos dados.

Aqui "forjam-se" e adulteram-se tokens, como faria um atacante, para confirmar
que a API os recusa a todos.
"""
import base64
import json
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app import config
from tests.api.ajudantes import CONTAS, cabecalho, iniciar_sessao

pytestmark = pytest.mark.api

ROTAS_PROTEGIDAS = [
    ("GET", "/api/conta"),
    ("GET", "/api/conta/movimentos"),
    ("GET", "/api/entidades"),
    ("POST", "/api/operacoes/transferencia"),
    ("POST", "/api/operacoes/levantamento"),
    ("POST", "/api/operacoes/pagamento"),
    ("POST", "/api/operacoes/qualquer-id/confirmar"),
    ("DELETE", "/api/operacoes/qualquer-id"),
    ("POST", "/api/auth/logout"),
]


def forjar_token(chave=config.CHAVE_JWT, algoritmo="HS256", **alteracoes):
    """Cria um token como o servidor o faria. As claims podem ser alteradas (ou retiradas com None)."""
    agora = datetime.now(timezone.utc)
    claims = {
        "sub": "ana",
        "iss": config.EMISSOR_JWT,
        "iat": agora,
        "exp": agora + timedelta(minutes=5),
        "jti": uuid.uuid4().hex,
    }
    claims.update(alteracoes)
    claims = {nome: valor for nome, valor in claims.items() if valor is not None}
    return jwt.encode(claims, chave, algorithm=algoritmo)


def adulterar(token: str, **alteracoes) -> str:
    """Altera o conteúdo de um token verdadeiro, mantendo a assinatura original."""
    parte_cabecalho, parte_conteudo, assinatura = token.split(".")
    conteudo = json.loads(base64.urlsafe_b64decode(parte_conteudo + "=" * (-len(parte_conteudo) % 4)))
    conteudo.update(alteracoes)
    novo_conteudo = base64.urlsafe_b64encode(json.dumps(conteudo).encode()).rstrip(b"=").decode()
    return f"{parte_cabecalho}.{novo_conteudo}.{assinatura}"


def pedir_conta(cliente, token):
    return cliente.get("/api/conta", headers=cabecalho(token))


@pytest.mark.parametrize("metodo, rota", ROTAS_PROTEGIDAS)
def test_rotas_protegidas_exigem_token(cliente, metodo, rota):
    resposta = cliente.request(metodo, rota)
    assert resposta.status_code == 401
    assert resposta.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize("valor", [
    "Bearer",
    "Bearer isto-nao-e-um-token",
    "Bearer abc.def.ghi",
    "Basic YW5hOkFuYUAyMDI2",   # outro esquema de autenticação ("ana:Ana@2026" em Base64)
], ids=["sem-token", "texto-qualquer", "formato-jwt-falso", "esquema-basic"])
def test_cabecalho_authorization_invalido_e_recusado(cliente, valor):
    assert cliente.get("/api/conta", headers={"Authorization": valor}).status_code == 401


def test_token_sem_a_palavra_bearer_e_recusado(cliente):
    token = iniciar_sessao(cliente, "ana")
    assert cliente.get("/api/conta", headers={"Authorization": token}).status_code == 401


def test_token_no_url_e_recusado(cliente):
    # Tokens no URL ficam registados em históricos e logs: a API só os aceita no cabeçalho
    token = iniciar_sessao(cliente, "ana")
    assert cliente.get(f"/api/conta?access_token={token}").status_code == 401


def test_controlo_token_forjado_com_a_chave_certa_e_aceite(cliente):
    # Teste de CONTROLO: prova que forjar_token() cria tokens que o servidor aceitaria.
    # Sem ele, os testes seguintes podiam passar pelos motivos errados.
    assert pedir_conta(cliente, forjar_token()).status_code == 200


def test_token_expirado_e_recusado(cliente):
    uma_hora_atras = datetime.now(timezone.utc) - timedelta(hours=1)
    token = forjar_token(iat=uma_hora_atras, exp=uma_hora_atras + timedelta(minutes=15))
    assert pedir_conta(cliente, token).status_code == 401


def test_token_assinado_com_outra_chave_e_recusado(cliente):
    token = forjar_token(chave="chave-do-atacante-com-mais-de-32-caracteres")
    assert pedir_conta(cliente, token).status_code == 401


def test_conteudo_adulterado_e_recusado(cliente):
    # A Ana altera o "sub" do seu próprio token para se fazer passar pelo Bruno
    token = adulterar(iniciar_sessao(cliente, "ana"), sub="bruno")
    assert pedir_conta(cliente, token).status_code == 401


def test_algoritmo_none_e_recusado(cliente):
    # Ataque clássico: um token SEM assinatura que declara usar o algoritmo "none"
    token = forjar_token(chave=None, algoritmo="none")
    assert pedir_conta(cliente, token).status_code == 401


def test_emissor_desconhecido_e_recusado(cliente):
    assert pedir_conta(cliente, forjar_token(iss="outro-sistema")).status_code == 401


def test_token_sem_identificador_jti_e_recusado(cliente):
    assert pedir_conta(cliente, forjar_token(jti=None)).status_code == 401


def test_token_de_utilizador_inexistente_e_recusado(cliente):
    assert pedir_conta(cliente, forjar_token(sub="mallory")).status_code == 401


def test_cada_token_so_da_acesso_a_conta_do_seu_titular(cliente, sessao_ana, sessao_bruno):
    assert cliente.get("/api/conta", headers=sessao_ana).json()["titular"] == "Ana Machava"
    assert cliente.get("/api/conta", headers=sessao_bruno).json()["titular"] == "Bruno Sitoe"


def test_nao_e_possivel_indicar_a_conta_de_origem(cliente, sessao_bruno):
    # O Bruno acrescenta um campo que a API não prevê, para tentar debitar a conta da Ana
    resposta = cliente.post(
        "/api/operacoes/transferencia",
        headers=sessao_bruno,
        json={"conta_origem": CONTAS["ana"], "conta_destino": CONTAS["bruno"], "valor": "100.00"},
    )
    assert resposta.status_code == 422
    assert "conta_origem" in resposta.json()["detail"]
