"""
Conversões de dinheiro.

Os valores são guardados em CENTAVOS (números inteiros) para evitar os erros de
arredondamento dos números em vírgula flutuante (em Python, 0.1 + 0.2 dá 0.30000000000000004).
"""
from decimal import Decimal


def para_centavos(valor: Decimal) -> int:
    """Decimal('1500.50') -> 150050"""
    return int((valor * 100).to_integral_exact())


def para_texto(centavos: int) -> str:
    """Formato usado pela API.  150050 -> '1500.50'   |   -2500 -> '-25.00'"""
    sinal = "-" if centavos < 0 else ""
    inteiro, resto = divmod(abs(centavos), 100)
    return f"{sinal}{inteiro}.{resto:02d}"


def formatar(centavos: int) -> str:
    """Formato mostrado às pessoas.  150050 -> '1 500,50 MZN'"""
    sinal = "-" if centavos < 0 else ""
    inteiro, resto = divmod(abs(centavos), 100)
    inteiro_com_espacos = f"{inteiro:,}".replace(",", " ")
    return f"{sinal}{inteiro_com_espacos},{resto:02d} MZN"
