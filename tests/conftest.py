"""
Configuração partilhada por TODOS os testes (unitários, de API e de interface).
"""
import pytest

from app.dados import bd


def pytest_addoption(parser):
    """Acrescenta a opção --headless à linha de comandos do pytest."""
    parser.addoption(
        "--headless", action="store_true", help="Testes de interface: executar o Chrome sem abrir janela"
    )


@pytest.fixture(autouse=True)
def dados_iniciais():
    """autouse=True: corre antes de CADA teste, sem ser pedida.
    Repõe os dados de demonstração, para que nenhum teste dependa do que outro fez."""
    bd.repor()
