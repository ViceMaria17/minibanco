# MiniBanco

Plataforma financeira fictícia para aprender testes de software com Python, pytest e Selenium.
Permite consultar o saldo, transferir, levantar e pagar. O acesso exige autenticação
OAuth2 com tokens JWT, e cada operação tem de ser confirmada com um PIN.

Todos os dados são fictícios e ficam em memória: voltam ao estado inicial sempre que o servidor reinicia.

## Instalação e arranque

Requisitos: Python 3.10 ou superior e, para os testes de interface, o Google Chrome.

```bash
python -m venv venv
venv\Scripts\activate            # Windows
# source venv/bin/activate       # Linux / macOS
pip install -r requirements.txt

uvicorn app.main:app --reload
```

- Aplicação: http://127.0.0.1:8000
- Documentação interactiva da API: http://127.0.0.1:8000/docs
  (o botão **Authorize** faz o login OAuth2; depois pode experimentar cada rota, como no Postman)

## Utilizadores de demonstração

| Utilizador | Senha        | PIN    | Conta       | Saldo inicial   |
|------------|--------------|--------|-------------|-----------------|
| `ana`      | `Ana@2026`   | `1234` | `100200300` | 50 000,00 MZN   |
| `bruno`    | `Bruno@2026` | `4321` | `100200301` | 1 500,00 MZN    |

Entidades para pagamentos: `10001` Electra Energia, `10002` Águas do Índico, `10003` Onda TV.

## Como funciona uma operação

```
1. Login            utilizador + senha  ──►  token JWT (válido 15 minutos)

2. Iniciar          dados + saldo verificados  ──►  operação PENDENTE (válida 2 minutos)
                    Nesta fase NENHUM valor é movimentado.

3. Confirmar        PIN verificado + saldo verificado OUTRA VEZ  ──►  operação executada
```

O saldo é verificado nas duas fases porque pode mudar entre elas (por exemplo, se outra
operação for confirmada entretanto).

## Regras de negócio

| Regra | Resposta |
|-------|----------|
| O valor tem de ser maior que zero, com no máximo 2 casas decimais | 422 |
| Nenhuma operação pode ultrapassar o saldo (usar o saldo todo é permitido) | 422 |
| Não se pode transferir para a própria conta nem para uma conta inexistente | 422 |
| Levantamentos: múltiplos de 100 MZN, até 20 000 MZN por operação | 422 |
| Pagamentos: entidade com 5 dígitos que exista; referência com 9 dígitos | 422 |
| A confirmação expira 2 minutos depois de a operação ser iniciada | 410 |

## Mecanismos de segurança

| Mecanismo | Onde está |
|-----------|-----------|
| Login OAuth2 (fluxo *password*) e token JWT assinado com HS256 | `app/seguranca.py` |
| Verificação de assinatura, expiração, emissor e algoritmo (recusa `none`) | `validar_token()` |
| Logout revoga o token (lista de `jti` revogados) | `revogar()` |
| Bloqueio de 5 minutos após 3 senhas ou PINs errados seguidos | `_registar_falha()` |
| A mesma mensagem e o mesmo tempo de resposta para "utilizador inexistente" e "senha errada" | `autenticar()` e `HASH_FICTICIO` |
| Senhas e PINs guardados com PBKDF2 e sal aleatório | `app/senhas.py` |
| Confirmação de cada operação com PIN (segunda autenticação) | `app/operacoes.py` |
| Uma operação só pode ser confirmada pelo dono, e uma única vez | `_obter_pendente()` e `confirmar()` |
| Campos não previstos são recusados (ex.: `conta_origem`) | `app/modelos.py` |
| Texto mostrado sempre com `textContent`, nunca `innerHTML` (protecção contra XSS) | `app/static/conta.js` |
| Cabeçalhos de segurança: CSP, `X-Frame-Options`, `Cache-Control: no-store` | `app/main.py` |

## API

| Método | Rota | Descrição | Respostas |
|--------|------|-----------|-----------|
| POST | `/api/auth/token` | Login (formulário: `username`, `password`) | 200, 401, 422, 423 |
| POST | `/api/auth/logout` | Termina a sessão e revoga o token | 204, 401 |
| GET | `/api/conta` | Titular, número de conta e saldo | 200, 401, 423 |
| GET | `/api/conta/movimentos` | Movimentos, do mais recente para o mais antigo | 200, 401, 423 |
| GET | `/api/entidades` | Entidades para pagamentos | 200, 401, 423 |
| POST | `/api/operacoes/transferencia` | Inicia uma transferência | 201, 401, 422, 423 |
| POST | `/api/operacoes/levantamento` | Inicia um levantamento | 201, 401, 422, 423 |
| POST | `/api/operacoes/pagamento` | Inicia um pagamento | 201, 401, 422, 423 |
| POST | `/api/operacoes/{id}/confirmar` | Confirma com o PIN | 200, 401, 403, 404, 410, 422, 423 |
| DELETE | `/api/operacoes/{id}` | Cancela uma operação pendente | 204, 401, 404, 423 |

Todas as rotas, excepto o login, exigem o cabeçalho `Authorization: Bearer <token>`.

## Testes

Os testes seguem a **pirâmide de testes**: muitos testes rápidos na base e poucos testes lentos no topo.

```
tests/
├── conftest.py              # repõe os dados antes de cada teste; opção --headless
├── unit/                    # 14 testes · funções isoladas · milissegundos
├── api/                     # 72 testes · pedidos HTTP sem navegador · poucos segundos
│   ├── test_autenticacao.py     login, bloqueio, logout
│   ├── test_tokens.py           tokens forjados, adulterados, expirados, sem token
│   ├── test_operacoes.py        saldo, regras de negócio, movimentos
│   └── test_confirmacao.py      PIN, repetição, operações alheias, expiração
└── ui/                      # 13 testes · Selenium com Chrome · ~30 segundos
    ├── paginas/                 Page Objects (login e conta)
    ├── test_login_ui.py         login, sessão, logout
    └── test_operacoes_ui.py     transferência, PIN, cancelamento, levantamento, XSS
```

### Como executar

```bash
pytest                    # todos os testes
pytest -m unit            # só os unitários
pytest -m api             # só os de API
pytest -m ui              # só os de interface (abre o Chrome)
pytest -m ui --headless   # interface, sem abrir janela
pytest -k pin             # só os testes com "pin" no nome
```

Os testes de interface arrancam o servidor sozinhos: não é preciso ter o `uvicorn` a correr.
Quando um teste de interface falha, é guardada uma captura de ecrã em `relatorios/capturas/`.

Variáveis de ambiente opcionais, úteis em integração contínua: `CHROME_BINARIO` (caminho do Chrome),
`CHROMEDRIVER` (caminho do driver) e `CI=1` (acrescenta `--no-sandbox`).

### Técnicas a observar nos testes

| Técnica | Onde ver |
|---------|----------|
| Fixtures, incluindo `autouse` e dependências entre fixtures | `tests/conftest.py`, `tests/api/conftest.py` |
| Testes parametrizados e valores-limite | `test_operacoes.py` |
| Avançar o relógio com `monkeypatch`, sem esperar | `test_bloqueio_termina_ao_fim_de_5_minutos` |
| Teste de controlo, que prova que a ferramenta de teste funciona | `test_controlo_token_forjado_com_a_chave_certa_e_aceite` |
| Forjar e adulterar tokens JWT | `forjar_token()` e `adulterar()` em `test_tokens.py` |
| Page Objects e localizadores `data-testid` | `tests/ui/paginas/` |
| Esperas explícitas, sem `time.sleep()` | `tests/ui/paginas/base.py` |
| Executar JavaScript no navegador | `test_token_adulterado_no_navegador_termina_a_sessao` |
| Hook do pytest para capturas de ecrã em falhas | `pytest_runtest_makereport` em `tests/ui/conftest.py` |
| Servidor arrancado pelo próprio teste, numa thread | fixture `url_base` em `tests/ui/conftest.py` |

## Exercícios propostos

1. **Pagamento na interface.** Escreva um teste Selenium para um pagamento completo. O Page Object já tem o método `pagar()`.
2. **Cabeçalhos de segurança.** Escreva um teste de API que confirme que as rotas `/api/` respondem com `Cache-Control: no-store` e que a página inicial tem `Content-Security-Policy`.
3. **Teste de mutação manual.** Em `app/operacoes.py`, apague a linha `exigir_saldo(conta, operacao.valor)` dentro de `confirmar()` e corra `pytest -m api`. Que teste falha? Reponha a linha e repita com outras protecções (por exemplo, a verificação `operacao.utilizador != conta.utilizador`). Se nenhum teste falhar, falta um teste.
4. **Valores-limite do levantamento na interface.** 20 000 MZN deve abrir a confirmação; 20 100 MZN deve mostrar o erro.
5. **PIN com formato inválido.** Confirme com um teste que três PINs como `12a4` não bloqueiam a conta (são recusados antes de contarem como tentativas).
6. **Plano de testes em Gherkin.** Escreva os cenários Dado/Quando/Então destas funcionalidades e indique, para cada um, o teste que o automatiza.
7. **Relatório HTML.** Instale o `pytest-html` e gere um relatório com `pytest --html=relatorios/relatorio.html --self-contained-html`.

## Simplificações (o que seria diferente em produção)

- O fluxo OAuth2 *password* é aqui usado por ser simples, mas está desaconselhado. Em produção usa-se o fluxo *Authorization Code* com PKCE e um servidor de autorização separado.
- Os dados ficam em memória. Em produção haveria uma base de dados com transacções.
- O token fica no `sessionStorage`. Um cookie `HttpOnly`, `Secure` e `SameSite` protege-o melhor contra XSS.
- Não há HTTPS, limite de pedidos por IP nem registo de auditoria.
- O PBKDF2 usa 100 000 iterações para os testes serem rápidos. A OWASP recomenda 600 000, ou Argon2.
