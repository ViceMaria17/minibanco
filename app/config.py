"""
Configurações da aplicação.

Os valores sensíveis podem ser definidos por variáveis de ambiente, sem mexer no código.
"""
import os
import secrets

# Chave secreta usada para ASSINAR os tokens JWT. Em produção viria de um cofre de segredos.
# Se não for definida, gera-se uma aleatória em cada arranque (os tokens antigos deixam de valer).
CHAVE_JWT = os.environ.get("MINIBANCO_CHAVE_JWT") or secrets.token_urlsafe(32)
ALGORITMO_JWT = "HS256"
EMISSOR_JWT = "minibanco"

MINUTOS_TOKEN_ACESSO = int(os.environ.get("MINIBANCO_MINUTOS_TOKEN", "15"))
SEGUNDOS_CONFIRMACAO = 120          # tempo para confirmar uma operação com o PIN

MAX_TENTATIVAS = 3                  # senhas ou PINs errados seguidos antes do bloqueio
MINUTOS_BLOQUEIO = 5

# Valores em CENTAVOS (ver dinheiro.py)
LEVANTAMENTO_MAXIMO = 20_000_00     # 20 000,00 MZN por operação
LEVANTAMENTO_MULTIPLO = 100_00      # só notas: múltiplos de 100,00 MZN

# PBKDF2: quanto mais iterações, mais lento (e caro) é adivinhar senhas por força bruta.
# A OWASP recomenda 600 000 em produção; aqui usa-se menos para os testes correrem depressa.
ITERACOES_HASH = 100_000
