"""
Hash de senhas e PINs com PBKDF2-SHA256 (biblioteca padrão do Python).

Nunca se guarda a senha em claro: guarda-se o resultado de uma função lenta e
irreversível, calculada com um "sal" aleatório diferente para cada segredo.
Formato guardado:  pbkdf2_sha256$<iterações>$<sal>$<resumo>
"""
import hashlib
import hmac
import secrets

from app.config import ITERACOES_HASH


def gerar_hash(segredo: str) -> str:
    sal = secrets.token_bytes(16)
    resumo = hashlib.pbkdf2_hmac("sha256", segredo.encode(), sal, ITERACOES_HASH)
    return f"pbkdf2_sha256${ITERACOES_HASH}${sal.hex()}${resumo.hex()}"


def verificar_hash(segredo: str, hash_guardado: str) -> bool:
    _, iteracoes, sal_hex, resumo_hex = hash_guardado.split("$")
    resumo = hashlib.pbkdf2_hmac("sha256", segredo.encode(), bytes.fromhex(sal_hex), int(iteracoes))
    # compare_digest demora o mesmo tempo, quer os valores difiram no primeiro byte quer no último
    # (uma comparação normal com == daria pistas a quem medisse o tempo de resposta).
    return hmac.compare_digest(resumo.hex(), resumo_hex)


# Usado quando o utilizador não existe: compara-se a senha com este hash na mesma,
# para que a resposta demore o mesmo tempo e não se revele quem tem conta.
HASH_FICTICIO = gerar_hash(secrets.token_urlsafe(16))
