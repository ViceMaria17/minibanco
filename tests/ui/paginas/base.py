"""
Classe base dos Page Objects: reúne as esperas explícitas num só sítio.
"""
from urllib.parse import urlparse

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


def testid(nome: str) -> tuple:
    """Localizador pelo atributo data-testid.
    Este atributo existe só para os testes: não muda quando o design ou os textos mudam."""
    return (By.CSS_SELECTOR, f"[data-testid='{nome}']")


class PaginaBase:
    def __init__(self, driver, url_base: str, timeout: int = 10):
        self.driver = driver
        self.url_base = url_base
        self.wait = WebDriverWait(driver, timeout)

    def visivel(self, localizador):
        """Espera que o elemento esteja visível e devolve-o."""
        return self.wait.until(EC.visibility_of_element_located(localizador))

    def clicar(self, localizador):
        """Espera que o elemento esteja visível e activo, e clica."""
        self.wait.until(EC.element_to_be_clickable(localizador)).click()

    def escrever(self, localizador, texto: str):
        campo = self.visivel(localizador)
        campo.clear()
        campo.send_keys(texto)

    def texto(self, localizador) -> str:
        return self.visivel(localizador).text

    def esperar_texto(self, localizador, parte: str) -> bool:
        """Espera até o elemento conter um certo texto. Devolve False se não acontecer a tempo."""
        try:
            return self.wait.until(EC.text_to_be_present_in_element(localizador, parte))
        except TimeoutException:
            return False

    def esta_visivel(self, localizador) -> bool:
        """Verifica AGORA, sem esperar, se o elemento está visível."""
        elementos = self.driver.find_elements(*localizador)
        return bool(elementos) and elementos[0].is_displayed()

    def caminho_e(self, caminho: str) -> bool:
        """Espera até o caminho do URL (sem domínio nem parâmetros) ser o indicado."""
        try:
            return self.wait.until(lambda driver: urlparse(driver.current_url).path == caminho)
        except TimeoutException:
            return False
