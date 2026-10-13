"""
Testes unitários: funções de conversão de dinheiro, testadas isoladamente.
"""
from decimal import Decimal

import pytest

from app.dinheiro import formatar, para_centavos, para_texto

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("valor, centavos", [
    (Decimal("0.01"), 1),
    (Decimal("1500.50"), 150050),
    (Decimal("20000"), 2000000),
])
def test_converte_decimal_para_centavos(valor, centavos):
    assert para_centavos(valor) == centavos


@pytest.mark.parametrize("centavos, texto", [
    (150050, "1500.50"),
    (5, "0.05"),
    (0, "0.00"),
    (-2500, "-25.00"),
])
def test_converte_centavos_para_o_formato_da_api(centavos, texto):
    assert para_texto(centavos) == texto


@pytest.mark.parametrize("centavos, texto", [
    (5_000_000, "50 000,00 MZN"),
    (150, "1,50 MZN"),
    (-123456, "-1 234,56 MZN"),
])
def test_formata_valores_para_mostrar_as_pessoas(centavos, texto):
    assert formatar(centavos) == texto
