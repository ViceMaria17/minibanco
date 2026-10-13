// Funções partilhadas pelas páginas: guardar o token e falar com a API.

const CHAVE_TOKEN = 'minibanco.token';

// O token fica no sessionStorage: desaparece quando o separador do navegador é fechado.
// (Numa aplicação real, um cookie HttpOnly protege melhor o token contra ataques XSS.)
export const sessao = {
  obter: () => sessionStorage.getItem(CHAVE_TOKEN),
  guardar: (token) => sessionStorage.setItem(CHAVE_TOKEN, token),
  limpar: () => sessionStorage.removeItem(CHAVE_TOKEN),
};

/** Apaga o token no navegador e volta à página de login, indicando o motivo. */
export function terminarSessao(motivo) {
  sessao.limpar();
  location.replace(`/?motivo=${motivo}`);
}

/** Extrai a mensagem de erro de uma resposta da API. */
export function textoErro(dados) {
  return typeof dados?.detail === 'string' ? dados.detail : 'Ocorreu um erro inesperado. Tente novamente.';
}

/**
 * Faz um pedido autenticado à API, com o token no cabeçalho Authorization.
 * Se a sessão for inválida (401) ou a conta estiver bloqueada (423), termina a sessão.
 * Devolve { ok, status, dados }.
 */
export async function api(caminho, { metodo = 'GET', corpo } = {}) {
  const token = sessao.obter();
  if (!token) return terminarEEsperar('sessao');

  const opcoes = { method: metodo, headers: { Authorization: `Bearer ${token}` } };
  if (corpo !== undefined) {
    opcoes.headers['Content-Type'] = 'application/json';
    opcoes.body = JSON.stringify(corpo);
  }

  let resposta;
  try {
    resposta = await fetch(caminho, opcoes);
  } catch {
    return { ok: false, status: 0, dados: { detail: 'Não foi possível contactar o servidor. Verifique a ligação.' } };
  }

  if (resposta.status === 401) return terminarEEsperar('sessao');
  if (resposta.status === 423) return terminarEEsperar('bloqueio');

  const dados = resposta.status === 204 ? null : await resposta.json().catch(() => null);
  return { ok: resposta.ok, status: resposta.status, dados };
}

// Muda de página e devolve uma promessa que nunca termina: o código que chamou api()
// fica parado até a página mudar, em vez de continuar com uma sessão inválida.
function terminarEEsperar(motivo) {
  terminarSessao(motivo);
  return new Promise(() => {});
}
