"""Page Object da página da conta (saldo, operações, confirmação com PIN e movimentos)."""
from decimal import Decimal

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select

from tests.ui.paginas.base import PaginaBase, testid


def texto_para_decimal(texto: str) -> Decimal:
    """'50 000,00 MZN' -> Decimal('50000.00')"""
    return Decimal(texto.replace("MZN", "").replace(" ", "").replace(",", "."))


class PaginaConta(PaginaBase):
    NOME_TITULAR = testid("nome-titular")
    SALDO = testid("saldo")
    BOTAO_SAIR = testid("botao-sair")
    MENSAGEM_SUCESSO = testid("mensagem-sucesso")
    MENSAGEM_ERRO = testid("mensagem-erro")
    MENSAGEM_INFO = testid("mensagem-info")
    MODAL = testid("modal-confirmacao")
    RESUMO = testid("resumo-operacao")
    CAMPO_PIN = testid("campo-pin")
    ERRO_PIN = testid("erro-pin")
    BOTAO_CONFIRMAR = testid("botao-confirmar")
    BOTAO_CANCELAR = testid("botao-cancelar")
    LINHAS_MOVIMENTOS = (By.CSS_SELECTOR, "[data-testid='tabela-movimentos'] [data-testid='movimento']")

    def abrir(self):
        self.driver.get(f"{self.url_base}/conta")
        return self

    def esperar_carregamento(self):
        """A página está pronta quando o saldo aparece (o texto passa a terminar em "MZN")."""
        self.wait.until(EC.text_to_be_present_in_element(self.SALDO, "MZN"))
        return self

    def recarregar(self):
        """Recarrega a página: mostra o que está guardado no servidor, e não só no ecrã."""
        self.driver.refresh()
        return self.esperar_carregamento()

    # ---------- Consultas ----------

    def nome_titular(self) -> str:
        return self.texto(self.NOME_TITULAR)

    def saldo(self) -> Decimal:
        return texto_para_decimal(self.texto(self.SALDO))

    def mensagem_sucesso(self) -> str:
        return self.texto(self.MENSAGEM_SUCESSO)

    def mensagem_erro(self) -> str:
        return self.texto(self.MENSAGEM_ERRO)

    def mensagem_info(self) -> str:
        return self.texto(self.MENSAGEM_INFO)

    def erro_pin(self) -> str:
        return self.texto(self.ERRO_PIN)

    def confirmacao_aberta(self) -> bool:
        return self.esta_visivel(self.MODAL)

    def resumo(self) -> dict:
        """Resumo mostrado na confirmação, como dicionário {rótulo: valor}."""
        caixa = self.visivel(self.RESUMO)
        rotulos = [dt.text for dt in caixa.find_elements(By.TAG_NAME, "dt")]
        valores = [dd.text for dd in caixa.find_elements(By.TAG_NAME, "dd")]
        return dict(zip(rotulos, valores))

    def movimentos(self) -> list[dict]:
        """Movimentos da tabela, do mais recente para o mais antigo."""
        resultado = []
        for linha in self.driver.find_elements(*self.LINHAS_MOVIMENTOS):
            data, descricao, valor, saldo = [celula.text for celula in linha.find_elements(By.TAG_NAME, "td")]
            resultado.append({
                "data": data,
                "descricao": descricao,
                "valor": texto_para_decimal(valor),
                "saldo": texto_para_decimal(saldo),
            })
        return resultado

    # ---------- Acções ----------

    def escolher_separador(self, nome: str):
        self.clicar(testid(f"separador-{nome}"))

    def transferir(self, conta_destino: str, valor: str, descricao: str = ""):
        """Preenche a transferência e clica em Continuar (abre a confirmação, se for válida)."""
        self.escolher_separador("transferencia")
        self.escrever(testid("campo-conta-destino"), conta_destino)
        self.escrever(testid("campo-valor-transferencia"), valor)
        self.escrever(testid("campo-descricao"), descricao)
        self.clicar(testid("botao-continuar-transferencia"))

    def levantar(self, valor: str):
        self.escolher_separador("levantamento")
        self.escrever(testid("campo-valor-levantamento"), valor)
        self.clicar(testid("botao-continuar-levantamento"))

    def pagar(self, entidade: str, referencia: str, valor: str):
        """entidade é o código de 5 dígitos (ex.: "10001")."""
        self.escolher_separador("pagamento")
        # As entidades chegam da API depois de a página abrir: espera-se pela opção pretendida
        self.wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, f"[data-testid='campo-entidade'] option[value='{entidade}']")
        ))
        Select(self.visivel(testid("campo-entidade"))).select_by_value(entidade)
        self.escrever(testid("campo-referencia"), referencia)
        self.escrever(testid("campo-valor-pagamento"), valor)
        self.clicar(testid("botao-continuar-pagamento"))

    def confirmar_com_pin(self, pin: str):
        self.escrever(self.CAMPO_PIN, pin)
        self.clicar(self.BOTAO_CONFIRMAR)

    def cancelar_confirmacao(self):
        self.clicar(self.BOTAO_CANCELAR)
        self.wait.until(EC.invisibility_of_element_located(self.MODAL))

    def sair(self):
        self.clicar(self.BOTAO_SAIR)
