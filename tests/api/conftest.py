"""
Fixtures dos testes de API.

O TestClient fala directamente com a aplicação FastAPI, dentro do mesmo processo:
não é preciso arrancar nenhum servidor, e os testes correm em milissegundos.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.api.ajudantes import cabecalho, iniciar_sessao


@pytest.fixture
def cliente():
    return TestClient(app)


@pytest.fixture
def sessao_ana(cliente):
    """DADO que a Ana tem sessão iniciada (devolve os cabeçalhos com o token dela)."""
    return cabecalho(iniciar_sessao(cliente, "ana"))


@pytest.fixture
def sessao_bruno(cliente):
    """DADO que o Bruno tem sessão iniciada."""
    return cabecalho(iniciar_sessao(cliente, "bruno"))
