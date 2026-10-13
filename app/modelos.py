"""
Modelos dos dados recebidos pela API.

O Pydantic valida-os automaticamente: se um campo faltar ou tiver um formato errado,
a rota nem chega a ser executada e a API responde 422.
"""
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

# Valor monetário: maior que zero, no máximo 2 casas decimais e 12 dígitos no total
Valor = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]


class Pedido(BaseModel):
    # Campos não previstos são recusados. Impede, por exemplo, que alguém envie
    # um campo "conta_origem" na esperança de debitar a conta de outra pessoa.
    model_config = ConfigDict(extra="forbid")


class PedidoTransferencia(Pedido):
    conta_destino: str = Field(pattern=r"^\d{9}$")
    valor: Valor
    descricao: str = Field(default="", max_length=60)


class PedidoLevantamento(Pedido):
    valor: Valor


class PedidoPagamento(Pedido):
    entidade: str = Field(pattern=r"^\d{5}$")
    referencia: str = Field(pattern=r"^\d{9}$")
    valor: Valor


class PedidoConfirmacao(Pedido):
    pin: str = Field(pattern=r"^\d{4}$")
