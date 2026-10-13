"""
Testes unitários: hash de senhas e PINs.
"""
import pytest

from app.senhas import gerar_hash, verificar_hash

pytestmark = pytest.mark.unit


def test_aceita_a_senha_correcta():
    assert verificar_hash("Ana@2026", gerar_hash("Ana@2026"))


def test_recusa_senha_errada():
    # Maiúsculas e minúsculas contam
    assert not verificar_hash("ana@2026", gerar_hash("Ana@2026"))


def test_mesma_senha_gera_hashes_diferentes():
    # Graças ao "sal" aleatório, duas pessoas com a mesma senha têm hashes diferentes
    assert gerar_hash("1234") != gerar_hash("1234")


def test_hash_nao_contem_a_senha():
    assert "Ana@2026" not in gerar_hash("Ana@2026")
