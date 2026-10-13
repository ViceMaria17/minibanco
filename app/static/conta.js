import { api, sessao, terminarSessao, textoErro } from './api.js';

/** Encontra um elemento pelo atributo data-testid (o mesmo que os testes Selenium usam). */
const el = (testid) => document.querySelector(`[data-testid="${testid}"]`);

const ROTAS = {
  transferencia: '/api/operacoes/transferencia',
  levantamento: '/api/operacoes/levantamento',
  pagamento: '/api/operacoes/pagamento',
};

const modal = el('modal-confirmacao');
let operacaoPendente = null;   // { id, formulario } da operação à espera do PIN
let temporizador = null;

// ---------- Formatação ----------

/** "50000.00" -> "50 000,00 MZN" */
function formatarMZN(valor) {
  const [inteiro, decimal] = Number(valor).toFixed(2).split('.');
  return `${inteiro.replace(/\B(?=(\d{3})+(?!\d))/g, ' ')},${decimal} MZN`;
}

function formatarData(iso) {
  return new Date(iso).toLocaleString('pt-PT', { dateStyle: 'short', timeStyle: 'short' });
}

/** Aceita "1 500,50" ou "1500.50" e devolve "1500.50", o formato que a API espera. */
function normalizarValor(texto) {
  return texto.replace(/\s/g, '').replace(',', '.');
}

// ---------- Mensagens ----------

function limparMensagens() {
  for (const tipo of ['sucesso', 'erro', 'info']) el(`mensagem-${tipo}`).hidden = true;
}

function mostrarMensagem(tipo, texto) {
  limparMensagens();
  const caixa = el(`mensagem-${tipo}`);
  caixa.textContent = texto;
  caixa.hidden = false;
}

// ---------- Carregar dados ----------

async function carregarConta() {
  const { ok, dados } = await api('/api/conta');
  if (!ok) return;
  el('nome-titular').textContent = dados.titular;
  el('numero-conta').textContent = dados.numero_conta;
  el('saldo').textContent = formatarMZN(dados.saldo);
}

async function carregarMovimentos() {
  const { ok, dados } = await api('/api/conta/movimentos');
  if (!ok) return;
  el('tabela-movimentos').tBodies[0].replaceChildren(...dados.map(linhaMovimento));
}

function linhaMovimento(movimento) {
  const linha = document.createElement('tr');
  linha.dataset.testid = 'movimento';
  const debito = movimento.valor.startsWith('-');
  linha.append(
    celula(formatarData(movimento.data), 'data'),
    celula(movimento.descricao, 'descricao'),
    celula(formatarMZN(movimento.valor), debito ? 'num debito' : 'num credito'),
    celula(formatarMZN(movimento.saldo_apos), 'num'),
  );
  return linha;
}

// textContent (e nunca innerHTML): um texto como "<img onerror=...>" aparece escrito e não é interpretado.
function celula(texto, classes) {
  const td = document.createElement('td');
  td.className = classes;
  td.textContent = texto;
  return td;
}

async function carregarEntidades() {
  const { ok, dados } = await api('/api/entidades');
  if (!ok) return;
  el('campo-entidade').replaceChildren(...dados.map(({ codigo, nome }) => new Option(`${nome} (${codigo})`, codigo)));
}

// ---------- Separadores ----------

function activarSeparador(nome) {
  document.querySelectorAll('[role="tab"]').forEach((separador) => {
    separador.setAttribute('aria-selected', String(separador.dataset.separador === nome));
  });
  document.querySelectorAll('form.painel').forEach((formulario) => {
    formulario.hidden = formulario.dataset.operacao !== nome;
  });
  limparMensagens();
}

// ---------- Fase 1: iniciar a operação ----------

async function iniciarOperacao(evento) {
  evento.preventDefault();
  const formulario = evento.currentTarget;
  limparMensagens();

  const vazio = [...formulario.elements].find((campo) => campo.name && campo.name !== 'descricao' && !campo.value.trim());
  if (vazio) {
    mostrarMensagem('erro', 'Preencha todos os campos obrigatórios.');
    vazio.focus();
    return;
  }

  const corpo = Object.fromEntries(new FormData(formulario));
  corpo.valor = normalizarValor(corpo.valor);

  const botao = formulario.querySelector('button[type="submit"]');
  botao.disabled = true;
  try {
    const { ok, dados } = await api(ROTAS[formulario.dataset.operacao], { metodo: 'POST', corpo });
    if (ok) abrirConfirmacao(dados, formulario);
    else mostrarMensagem('erro', textoErro(dados));
  } finally {
    botao.disabled = false;
  }
}

// ---------- Fase 2: confirmar com o PIN ----------

function abrirConfirmacao(dados, formulario) {
  operacaoPendente = { id: dados.operacao_id, formulario };
  const resumo = el('resumo-operacao');
  resumo.replaceChildren();
  for (const { rotulo, valor } of dados.resumo) {
    const termo = document.createElement('dt');
    termo.textContent = rotulo;
    const definicao = document.createElement('dd');
    definicao.textContent = valor;
    resumo.append(termo, definicao);
  }
  el('campo-pin').value = '';
  el('erro-pin').hidden = true;
  iniciarContador(dados.expira_em_segundos);
  modal.showModal();
  el('campo-pin').focus();
}

function iniciarContador(segundos) {
  const fim = Date.now() + segundos * 1000;
  const actualizar = () => {
    const restante = Math.max(0, Math.ceil((fim - Date.now()) / 1000));
    el('contador').textContent = `${Math.floor(restante / 60)}:${String(restante % 60).padStart(2, '0')}`;
    if (restante === 0) {
      fecharConfirmacao();
      mostrarMensagem('erro', 'O tempo para confirmar terminou. Inicie a operação novamente.');
    }
  };
  clearInterval(temporizador);
  actualizar();
  temporizador = setInterval(actualizar, 1000);
}

function fecharConfirmacao() {
  clearInterval(temporizador);
  operacaoPendente = null;
  if (modal.open) modal.close();
}

function textoSucesso(dados) {
  let texto = dados.mensagem;
  if (dados.codigo_levantamento) texto += `\nCódigo de levantamento: ${dados.codigo_levantamento}.`;
  if (dados.comprovativo) texto += `\nComprovativo: ${dados.comprovativo}.`;
  return texto;
}

async function confirmarOperacao(evento) {
  evento.preventDefault();
  if (!operacaoPendente) return;
  const { id, formulario } = operacaoPendente;
  const botao = el('botao-confirmar');
  botao.disabled = true;
  try {
    const pin = el('campo-pin').value.trim();
    const { ok, status, dados } = await api(`/api/operacoes/${id}/confirmar`, { metodo: 'POST', corpo: { pin } });

    if (ok) {
      fecharConfirmacao();
      formulario.reset();
      // Os dados são actualizados ANTES de aparecer a mensagem: quando um teste
      // vê a mensagem de sucesso, o saldo e os movimentos já estão certos.
      await Promise.all([carregarConta(), carregarMovimentos()]);
      mostrarMensagem('sucesso', textoSucesso(dados));
      return;
    }

    // PIN errado (403) ou com formato inválido (422 de validação): fica no modal para tentar de novo
    if (status === 403 || (status === 422 && Array.isArray(dados?.erros))) {
      el('erro-pin').textContent = textoErro(dados);
      el('erro-pin').hidden = false;
      el('campo-pin').value = '';
      el('campo-pin').focus();
      return;
    }

    // Outros erros (tempo esgotado, saldo entretanto insuficiente...): fecha o modal
    fecharConfirmacao();
    mostrarMensagem('erro', textoErro(dados));
  } finally {
    botao.disabled = false;
  }
}

async function cancelarOperacao() {
  const id = operacaoPendente?.id;
  fecharConfirmacao();
  if (id) await api(`/api/operacoes/${id}`, { metodo: 'DELETE' });
  mostrarMensagem('info', 'Operação cancelada. Nenhum valor foi movimentado.');
}

// ---------- Ligações aos botões e formulários ----------

document.querySelectorAll('[role="tab"]').forEach((separador) => {
  separador.addEventListener('click', () => activarSeparador(separador.dataset.separador));
});
document.querySelectorAll('form.painel').forEach((formulario) => {
  formulario.addEventListener('submit', iniciarOperacao);
});
document.getElementById('form-pin').addEventListener('submit', confirmarOperacao);
el('botao-cancelar').addEventListener('click', cancelarOperacao);
modal.addEventListener('cancel', (evento) => {   // tecla Esc
  evento.preventDefault();
  cancelarOperacao();
});
el('botao-sair').addEventListener('click', async () => {
  await api('/api/auth/logout', { metodo: 'POST' });   // o servidor revoga o token
  terminarSessao('saida');
});

// ---------- Arranque ----------

if (!sessao.obter()) {
  terminarSessao('sessao');
} else {
  activarSeparador('transferencia');
  carregarConta();
  carregarMovimentos();
  carregarEntidades();
}
