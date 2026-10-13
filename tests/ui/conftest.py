"""
Fixtures dos testes de interface (Selenium).

O servidor da aplicação é arrancado automaticamente numa thread, numa porta livre,
uma única vez para toda a execução (scope="session"). Como corre no mesmo processo
que os testes, a fixture dados_iniciais (tests/conftest.py) também o repõe antes de cada teste.
"""
import os
import socket
import threading
import time
from pathlib import Path

import pytest
import uvicorn
from selenium import webdriver
from selenium.webdriver.chrome.service import Service

from app.main import app
from tests.ui.paginas.conta import PaginaConta
from tests.ui.paginas.login import PaginaLogin

PASTA_CAPTURAS = Path("relatorios/capturas")


def _porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))      # porta 0 = "o sistema escolhe uma porta livre"
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def url_base():
    """Arranca o MiniBanco uma vez e devolve o endereço, por exemplo http://127.0.0.1:53817"""
    porta = _porta_livre()
    servidor = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=porta, log_level="warning"))
    thread = threading.Thread(target=servidor.run, daemon=True)
    thread.start()
    limite = time.monotonic() + 10
    while not servidor.started:
        if time.monotonic() > limite:
            raise RuntimeError("O servidor não arrancou em 10 segundos.")
        time.sleep(0.05)
    yield f"http://127.0.0.1:{porta}"
    servidor.should_exit = True
    thread.join(timeout=5)


@pytest.fixture
def driver(request):
    """Um Chrome novo para cada teste, fechado no fim (passe ou falhe)."""
    opcoes = webdriver.ChromeOptions()
    if request.config.getoption("--headless"):
        opcoes.add_argument("--headless=new")
    opcoes.add_argument("--window-size=1366,900")

    # Variáveis de ambiente opcionais, úteis em servidores de integração contínua (CI)
    if os.environ.get("CHROME_BINARIO"):
        opcoes.binary_location = os.environ["CHROME_BINARIO"]
    if os.environ.get("CI"):
        opcoes.add_argument("--no-sandbox")
        opcoes.add_argument("--disable-dev-shm-usage")
    servico = Service(os.environ["CHROMEDRIVER"]) if os.environ.get("CHROMEDRIVER") else None

    navegador = webdriver.Chrome(options=opcoes, service=servico)
    yield navegador
    navegador.quit()


@pytest.fixture
def pagina_login(driver, url_base):
    """DADO que estou na página de login."""
    return PaginaLogin(driver, url_base).abrir()


@pytest.fixture
def conta_ana(pagina_login, driver, url_base):
    """DADO que a Ana iniciou sessão e está na página da conta."""
    pagina_login.entrar("ana", "Ana@2026")
    return PaginaConta(driver, url_base).esperar_carregamento()


@pytest.fixture
def conta_bruno(pagina_login, driver, url_base):
    """DADO que o Bruno iniciou sessão e está na página da conta."""
    pagina_login.entrar("bruno", "Bruno@2026")
    return PaginaConta(driver, url_base).esperar_carregamento()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Quando um teste de interface falha, guarda uma captura de ecrã para ajudar a perceber porquê."""
    resultado = yield
    relatorio = resultado.get_result()
    navegador = item.funcargs.get("driver")
    if relatorio.when == "call" and relatorio.failed and navegador is not None:
        PASTA_CAPTURAS.mkdir(parents=True, exist_ok=True)
        navegador.save_screenshot(str(PASTA_CAPTURAS / f"{item.name}.png"))
