"""
Relógio da aplicação.

O código pergunta as horas a esta função em vez de chamar datetime.now() directamente.
Assim, nos testes, é possível "avançar no tempo" com o monkeypatch do pytest
(por exemplo, para verificar que um bloqueio termina ao fim de 5 minutos sem esperar 5 minutos).

Importante: o resto do código usa `relogio.agora()` (e não `from app.relogio import agora`),
para que a substituição feita nos testes seja vista por todos.
"""
from datetime import datetime, timezone


def agora() -> datetime:
    return datetime.now(timezone.utc)
