"""Page Object da página de login."""
from tests.ui.paginas.base import PaginaBase, testid


class PaginaLogin(PaginaBase):
    CAMPO_UTILIZADOR = testid("campo-utilizador")
    CAMPO_SENHA = testid("campo-senha")
    BOTAO_ENTRAR = testid("botao-entrar")
    MENSAGEM_ERRO = testid("mensagem-erro")
    MENSAGEM_INFO = testid("mensagem-info")

    def abrir(self):
        self.driver.get(f"{self.url_base}/")
        self.visivel(self.CAMPO_UTILIZADOR)
        return self

    def entrar(self, utilizador: str, senha: str):
        self.escrever(self.CAMPO_UTILIZADOR, utilizador)
        self.escrever(self.CAMPO_SENHA, senha)
        self.clicar(self.BOTAO_ENTRAR)

    def mensagem_erro(self) -> str:
        return self.texto(self.MENSAGEM_ERRO)

    def mensagem_info(self) -> str:
        return self.texto(self.MENSAGEM_INFO)

    def esta_na_pagina(self) -> bool:
        return self.caminho_e("/")
