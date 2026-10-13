"""
"Base de dados" em memória.

Para uma aplicação de aprendizagem basta guardar tudo em dicionários.
O método repor() devolve os dados ao estado inicial: os testes chamam-no antes de
cada teste, para que nenhum teste dependa do que outro fez.
"""
import threading
from dataclasses import dataclass, field
from datetime import datetime

from app import relogio
from app.senhas import gerar_hash


@dataclass
class Movimento:
    data: datetime
    descricao: str
    valor: int          # centavos; negativo = débito, positivo = crédito
    saldo_apos: int


@dataclass
class Conta:
    utilizador: str
    titular: str
    numero: str
    hash_senha: str
    hash_pin: str
    saldo: int          # centavos
    movimentos: list[Movimento] = field(default_factory=list)


@dataclass
class OperacaoPendente:
    id: str
    utilizador: str
    tipo: str           # "transferencia" | "levantamento" | "pagamento"
    valor: int          # centavos
    detalhes: dict
    expira_em: datetime


# Entidades a quem se podem fazer pagamentos (código de 5 dígitos -> nome)
ENTIDADES = {
    "10001": "Electra Energia",
    "10002": "Águas do Índico",
    "10003": "Onda TV",
}

# Utilizadores de demonstração: (utilizador, titular, n.º de conta, senha, PIN, saldo em centavos)
_SEMENTE = [
    ("ana", "Ana Machava", "100200300", "Ana@2026", "1234", 50_000_00),
    ("bruno", "Bruno Sitoe", "100200301", "Bruno@2026", "4321", 1_500_00),
]

# Os hashes são lentos de calcular (de propósito), por isso calculam-se uma única vez.
_HASHES = {u: (gerar_hash(senha), gerar_hash(pin)) for u, _, _, senha, pin, _ in _SEMENTE}


class BaseDados:
    def __init__(self):
        # Trinco: impede que dois pedidos simultâneos alterem os mesmos dados ao mesmo tempo
        self.trinco = threading.RLock()
        self.repor()

    def repor(self) -> None:
        """Volta ao estado inicial: saldos originais, sem sessões, bloqueios nem operações pendentes."""
        with self.trinco:
            self.contas: dict[str, Conta] = {}
            for utilizador, titular, numero, _, _, saldo in _SEMENTE:
                hash_senha, hash_pin = _HASHES[utilizador]
                conta = Conta(utilizador, titular, numero, hash_senha, hash_pin, saldo)
                conta.movimentos.append(Movimento(relogio.agora(), "Depósito inicial", saldo, saldo))
                self.contas[utilizador] = conta
            self.operacoes: dict[str, OperacaoPendente] = {}
            self.tokens_revogados: set[str] = set()   # "jti" dos tokens terminados com logout
            self.falhas_senha: dict[str, int] = {}
            self.falhas_pin: dict[str, int] = {}
            self.bloqueios: dict[str, datetime] = {}  # utilizador -> fim do bloqueio

    def conta_por_numero(self, numero: str) -> Conta | None:
        return next((c for c in self.contas.values() if c.numero == numero), None)


bd = BaseDados()
