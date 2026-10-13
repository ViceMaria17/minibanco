import { sessao, textoErro } from './api.js';

// Mensagens mostradas quando se chega ao login vindo de outra página (/?motivo=...)
const MOTIVOS = {
  sessao: 'A sessão expirou ou não é válida. Inicie sessão novamente.',
  saida: 'Sessão terminada.',
  bloqueio: 'A conta foi bloqueada temporariamente por excesso de tentativas falhadas. Tente novamente dentro de alguns minutos.',
};

const formulario = document.getElementById('form-login');
const campoUtilizador = document.getElementById('utilizador');
const campoSenha = document.getElementById('senha');
const botaoEntrar = document.querySelector('[data-testid="botao-entrar"]');
const caixaInfo = document.querySelector('[data-testid="mensagem-info"]');
const caixaErro = document.querySelector('[data-testid="mensagem-erro"]');

// Quem já tem sessão iniciada segue directamente para a conta
if (sessao.obter()) {
  location.replace('/conta');
}

// Só se mostram textos fixos: o valor que vem no URL nunca é escrito na página
// (escrevê-lo abriria a porta a um ataque de XSS reflectido).
const motivo = new URLSearchParams(location.search).get('motivo');
if (motivo && Object.hasOwn(MOTIVOS, motivo)) {
  caixaInfo.textContent = MOTIVOS[motivo];
  caixaInfo.hidden = false;
}

function mostrarErro(texto) {
  caixaErro.textContent = texto;
  caixaErro.hidden = false;
}

formulario.addEventListener('submit', async (evento) => {
  evento.preventDefault();   // impede o envio "clássico" do formulário (que recarregaria a página)
  caixaErro.hidden = true;
  caixaInfo.hidden = true;

  const utilizador = campoUtilizador.value.trim();
  const senha = campoSenha.value;
  if (!utilizador || !senha) {
    mostrarErro('Indique o utilizador e a senha.');
    return;
  }

  botaoEntrar.disabled = true;
  try {
    // OAuth2, fluxo "password": as credenciais seguem como formulário, e não como JSON
    const resposta = await fetch('/api/auth/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ grant_type: 'password', username: utilizador, password: senha }),
    });
    const dados = await resposta.json();
    if (resposta.ok) {
      sessao.guardar(dados.access_token);
      location.replace('/conta');
      return;
    }
    mostrarErro(textoErro(dados));
    campoSenha.value = '';
    campoSenha.focus();
  } catch {
    mostrarErro('Não foi possível contactar o servidor. Verifique a ligação.');
  } finally {
    botaoEntrar.disabled = false;
  }
});
