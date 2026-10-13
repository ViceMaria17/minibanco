"""
Autenticação e autorização.

- Login com OAuth2 (fluxo "password"): o cliente envia o utilizador e a senha e recebe um
  token JWT (o "access token"), que passa a enviar em cada pedido no cabeçalho
  Authorization: Bearer <token>.
- O JWT é ASSINADO (HS256), mas não é cifrado: qualquer pessoa consegue ler o conteúdo,
  mas ninguém o consegue alterar sem a chave secreta.
- Senhas e PINs errados contam tentativas; à terceira falha seguida, a conta fica bloqueada.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

from app import config, relogio
from app.dados import Conta, bd
from app.senhas import HASH_FICTICIO, verificar_hash

# Indica onde se obtém o token (e activa o botão "Authorize" na documentação em /docs).
# auto_error=False: quando o token falta, somos nós a responder, com a nossa mensagem.
esquema_oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)

# A norma OAuth2 (RFC 6750) manda incluir este cabeçalho nas respostas 401
CABECALHO_BEARER = {"WWW-Authenticate": "Bearer"}


def erro_401(mensagem: str = "Sessão inválida ou expirada. Inicie sessão novamente.") -> HTTPException:
    return HTTPException(status_code=401, detail=mensagem, headers=CABECALHO_BEARER)


def erro_bloqueio() -> HTTPException:
    return HTTPException(
        status_code=423,
        detail=f"Demasiadas tentativas falhadas. A conta ficou bloqueada durante {config.MINUTOS_BLOQUEIO} minutos.",
    )


# ---------- Bloqueio por tentativas falhadas ----------

def verificar_bloqueio(utilizador: str) -> None:
    """Responde 423 se a conta estiver bloqueada. Se o bloqueio já terminou, limpa-o."""
    with bd.trinco:
        fim = bd.bloqueios.get(utilizador)
        if fim is None:
            return
        if relogio.agora() < fim:
            raise HTTPException(status_code=423, detail="A conta está bloqueada temporariamente. Tente novamente mais tarde.")
        del bd.bloqueios[utilizador]
        bd.falhas_senha.pop(utilizador, None)
        bd.falhas_pin.pop(utilizador, None)


def _registar_falha(contador: dict, utilizador: str) -> int:
    """Conta mais uma falha e, ao atingir o limite, bloqueia a conta. Devolve as tentativas restantes."""
    with bd.trinco:
        contador[utilizador] = contador.get(utilizador, 0) + 1
        restantes = config.MAX_TENTATIVAS - contador[utilizador]
        if restantes <= 0:
            bd.bloqueios[utilizador] = relogio.agora() + timedelta(minutes=config.MINUTOS_BLOQUEIO)
        return restantes


# ---------- Login e tokens ----------

def autenticar(utilizador: str, senha: str) -> dict:
    verificar_bloqueio(utilizador)
    conta = bd.contas.get(utilizador)
    # Se o utilizador não existir, compara-se a senha com um hash fictício na mesma,
    # para que a resposta demore o mesmo tempo (não se revela quem tem conta).
    senha_certa = verificar_hash(senha, conta.hash_senha if conta else HASH_FICTICIO)
    if conta is None or not senha_certa:
        if _registar_falha(bd.falhas_senha, utilizador) <= 0:
            raise erro_bloqueio()
        # A mesma mensagem para "utilizador inexistente" e para "senha errada"
        raise erro_401("Utilizador ou senha inválidos.")
    with bd.trinco:
        bd.falhas_senha.pop(utilizador, None)
    return criar_token_acesso(utilizador)


def criar_token_acesso(utilizador: str) -> dict:
    # Os tokens usam o relógio real (e não relogio.agora()) porque a biblioteca PyJWT
    # verifica a expiração com o relógio real.
    agora = datetime.now(timezone.utc)
    validade = timedelta(minutes=config.MINUTOS_TOKEN_ACESSO)
    claims = {
        "sub": utilizador,               # a quem pertence o token
        "iss": config.EMISSOR_JWT,       # quem o emitiu
        "iat": agora,                    # quando foi emitido
        "exp": agora + validade,         # quando expira
        "jti": uuid.uuid4().hex,         # identificador único (permite revogá-lo no logout)
    }
    token = jwt.encode(claims, config.CHAVE_JWT, algorithm=config.ALGORITMO_JWT)
    return {"access_token": token, "token_type": "bearer", "expires_in": int(validade.total_seconds())}


def validar_token(token: str | None) -> dict:
    """Verifica a assinatura, o emissor, a expiração e a revogação. Devolve as claims."""
    if not token:
        raise erro_401("Autenticação necessária.")
    try:
        claims = jwt.decode(
            token,
            config.CHAVE_JWT,
            algorithms=[config.ALGORITMO_JWT],   # lista fechada: recusa "none" e outros algoritmos
            issuer=config.EMISSOR_JWT,
            options={"require": ["sub", "iss", "iat", "exp", "jti"]},
        )
    except jwt.InvalidTokenError:
        # Assinatura errada, expirado, malformado, emissor errado... a resposta é sempre igual
        raise erro_401()
    if claims["jti"] in bd.tokens_revogados:
        raise erro_401()
    return claims


def revogar(claims: dict) -> None:
    with bd.trinco:
        bd.tokens_revogados.add(claims["jti"])


# ---------- Dependências usadas pelas rotas (o FastAPI executa-as antes da rota) ----------

def claims_do_token(token: Annotated[str | None, Depends(esquema_oauth2)]) -> dict:
    return validar_token(token)


def conta_autenticada(claims: Annotated[dict, Depends(claims_do_token)]) -> Conta:
    conta = bd.contas.get(claims["sub"])
    if conta is None:
        raise erro_401()
    verificar_bloqueio(conta.utilizador)
    return conta


ClaimsToken = Annotated[dict, Depends(claims_do_token)]
ContaAutenticada = Annotated[Conta, Depends(conta_autenticada)]


# ---------- Confirmação de operações com o PIN ----------

def verificar_pin(conta: Conta, pin: str) -> None:
    if verificar_hash(pin, conta.hash_pin):
        with bd.trinco:
            bd.falhas_pin.pop(conta.utilizador, None)
        return
    restantes = _registar_falha(bd.falhas_pin, conta.utilizador)
    if restantes <= 0:
        raise erro_bloqueio()
    tentativas = "Resta 1 tentativa" if restantes == 1 else f"Restam {restantes} tentativas"
    raise HTTPException(status_code=403, detail=f"PIN incorrecto. {tentativas}.")
