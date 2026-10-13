"""
Funções auxiliares dos testes de API (evitam repetir o mesmo código em cada teste).
"""
from decimal import Decimal

SENHAS = {"ana": "Ana@2026", "bruno": "Bruno@2026"}
PINS = {"ana": "1234", "bruno": "4321"}
CONTAS = {"ana": "100200300", "bruno": "100200301"}


def iniciar_sessao(cliente, utilizador: str) -> str:
    """Faz login (OAuth2, fluxo password) e devolve o access token."""
    resposta = cliente.post("/api/auth/token", data={"username": utilizador, "password": SENHAS[utilizador]})
    assert resposta.status_code == 200, resposta.text
    return resposta.json()["access_token"]


def cabecalho(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def saldo(cliente, cabecalhos: dict) -> Decimal:
    return Decimal(cliente.get("/api/conta", headers=cabecalhos).json()["saldo"])


def iniciar(cliente, cabecalhos: dict, operacao: str, **dados):
    """Fase 1: inicia uma operação (transferencia, levantamento ou pagamento)."""
    return cliente.post(f"/api/operacoes/{operacao}", json=dados, headers=cabecalhos)


def confirmar(cliente, cabecalhos: dict, operacao_id: str, pin: str):
    """Fase 2: confirma uma operação pendente com o PIN."""
    return cliente.post(f"/api/operacoes/{operacao_id}/confirmar", json={"pin": pin}, headers=cabecalhos)


def executar(cliente, cabecalhos: dict, operacao: str, pin: str, **dados):
    """Inicia e confirma uma operação de uma só vez. Devolve a resposta da confirmação."""
    resposta = iniciar(cliente, cabecalhos, operacao, **dados)
    assert resposta.status_code == 201, resposta.text
    return confirmar(cliente, cabecalhos, resposta.json()["operacao_id"], pin)
