"""
Ponto de entrada da aplicação MiniBanco: rotas da API e das páginas web.

Arrancar:  uvicorn app.main:app --reload
Depois abrir http://127.0.0.1:8000 (aplicação) ou http://127.0.0.1:8000/docs (API).
"""
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles

from app import operacoes, seguranca
from app.dados import ENTIDADES
from app.dinheiro import para_texto
from app.modelos import PedidoConfirmacao, PedidoLevantamento, PedidoPagamento, PedidoTransferencia
from app.seguranca import ClaimsToken, ContaAutenticada

PASTA_WEB = Path(__file__).parent / "static"

app = FastAPI(
    title="MiniBanco",
    description="Plataforma financeira fictícia para aprender testes de software. Todos os dados são fictícios.",
    version="1.0.0",
)
app.mount("/static", StaticFiles(directory=PASTA_WEB), name="static")


# ---------- Cabeçalhos de segurança em todas as respostas ----------

@app.middleware("http")
async def cabecalhos_seguranca(request: Request, chamar_rota):
    resposta = await chamar_rota(request)
    resposta.headers["X-Content-Type-Options"] = "nosniff"     # o navegador não "adivinha" o tipo de ficheiro
    resposta.headers["X-Frame-Options"] = "DENY"               # a página não pode ser embutida noutro site
    resposta.headers["Referrer-Policy"] = "no-referrer"
    if not request.url.path.startswith(("/docs", "/redoc")):   # a documentação usa scripts externos
        # Só se carregam scripts e estilos do próprio site: bloqueia scripts injectados (XSS)
        resposta.headers["Content-Security-Policy"] = (
            "default-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        )
    if request.url.path.startswith("/api/"):
        resposta.headers["Cache-Control"] = "no-store"         # dados financeiros nunca ficam em cache
    return resposta


# ---------- Erros de validação com mensagens em português ----------

NOMES_CAMPOS = {
    "username": "utilizador", "password": "senha", "pin": "PIN", "valor": "valor",
    "conta_destino": "conta de destino", "descricao": "descrição", "entidade": "entidade",
    "referencia": "referência", "body": "corpo do pedido",
}

MENSAGENS_VALIDACAO = {
    "missing": "é obrigatório",
    "greater_than": "tem de ser superior a zero",
    "decimal_parsing": "tem de ser um número",
    "decimal_type": "tem de ser um número",
    "finite_number": "tem de ser um número",
    "decimal_max_places": "admite no máximo 2 casas decimais",
    "decimal_max_digits": "é demasiado grande",
    "decimal_whole_digits": "é demasiado grande",
    "string_type": "tem de ser texto",
    "string_pattern_mismatch": "tem um formato inválido",
    "string_too_long": "é demasiado longo",
    "extra_forbidden": "não é permitido",
}


@app.exception_handler(RequestValidationError)
async def erro_de_validacao(request: Request, erro: RequestValidationError):
    mensagens = []
    for e in erro.errors():
        if e["type"] == "json_invalid":
            mensagens.append("O corpo do pedido não é um JSON válido.")
            continue
        campo = str(e["loc"][-1]) if e.get("loc") else "body"
        nome = NOMES_CAMPOS.get(campo, campo)
        mensagens.append(f"O campo «{nome}» {MENSAGENS_VALIDACAO.get(e['type'], 'tem um valor inválido')}.")
    return JSONResponse(status_code=422, content={"detail": " ".join(mensagens), "erros": mensagens})


# ---------- Páginas ----------

@app.get("/", include_in_schema=False)
def pagina_login():
    return FileResponse(PASTA_WEB / "login.html")


@app.get("/conta", include_in_schema=False)
def pagina_conta():
    return FileResponse(PASTA_WEB / "conta.html")


# ---------- Autenticação ----------

@app.post("/api/auth/token", tags=["Autenticação"], summary="Login (OAuth2, fluxo password)")
def obter_token(formulario: Annotated[OAuth2PasswordRequestForm, Depends()]):
    return seguranca.autenticar(formulario.username, formulario.password)


@app.post("/api/auth/logout", status_code=204, tags=["Autenticação"], summary="Terminar sessão (revoga o token)")
def terminar_sessao(claims: ClaimsToken):
    seguranca.revogar(claims)


# ---------- Conta ----------

@app.get("/api/conta", tags=["Conta"], summary="Titular, número de conta e saldo")
def consultar_conta(conta: ContaAutenticada):
    return {"titular": conta.titular, "numero_conta": conta.numero, "saldo": para_texto(conta.saldo), "moeda": "MZN"}


@app.get("/api/conta/movimentos", tags=["Conta"], summary="Movimentos, do mais recente para o mais antigo")
def listar_movimentos(conta: ContaAutenticada):
    return [
        {"data": m.data.isoformat(), "descricao": m.descricao, "valor": para_texto(m.valor), "saldo_apos": para_texto(m.saldo_apos)}
        for m in reversed(conta.movimentos)
    ]


@app.get("/api/entidades", tags=["Conta"], summary="Entidades disponíveis para pagamentos")
def listar_entidades(conta: ContaAutenticada):
    return [{"codigo": codigo, "nome": nome} for codigo, nome in ENTIDADES.items()]


# ---------- Operações (fase 1: iniciar) ----------

@app.post("/api/operacoes/transferencia", status_code=201, tags=["Operações"], summary="Iniciar transferência")
def iniciar_transferencia(pedido: PedidoTransferencia, conta: ContaAutenticada):
    return operacoes.iniciar_transferencia(conta, pedido)


@app.post("/api/operacoes/levantamento", status_code=201, tags=["Operações"], summary="Iniciar levantamento")
def iniciar_levantamento(pedido: PedidoLevantamento, conta: ContaAutenticada):
    return operacoes.iniciar_levantamento(conta, pedido)


@app.post("/api/operacoes/pagamento", status_code=201, tags=["Operações"], summary="Iniciar pagamento")
def iniciar_pagamento(pedido: PedidoPagamento, conta: ContaAutenticada):
    return operacoes.iniciar_pagamento(conta, pedido)


# ---------- Operações (fase 2: confirmar com PIN ou cancelar) ----------

@app.post("/api/operacoes/{operacao_id}/confirmar", tags=["Operações"], summary="Confirmar operação com o PIN")
def confirmar_operacao(operacao_id: str, pedido: PedidoConfirmacao, conta: ContaAutenticada):
    return operacoes.confirmar(conta, operacao_id, pedido.pin)


@app.delete("/api/operacoes/{operacao_id}", status_code=204, tags=["Operações"], summary="Cancelar operação pendente")
def cancelar_operacao(operacao_id: str, conta: ContaAutenticada):
    operacoes.cancelar(conta, operacao_id)
