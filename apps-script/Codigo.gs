/**
 * Trampo com IA · inscrições da newsletter.
 *
 * Roda no Google Apps Script da conta do Arthur, de graça. Guarda os inscritos numa planilha PRIVADA,
 * faz a confirmação por e-mail (dupla confirmação) e o descadastro. O PC pede a lista com uma chave secreta
 * na hora de mandar as vagas do dia (hub/newsletter.py).
 *
 * Endereços (o mesmo /exec):
 *   POST acao=inscrever  email, consentimento=sim, areas, origem   (vem do formulário do site)
 *   GET  ?acao=confirmar&t=TOKEN                                     (link do e-mail de confirmação)
 *   GET  ?acao=sair&t=TOKEN    · POST acao=sair&t=TOKEN               (link de descadastro / um clique do Gmail)
 *   GET  ?acao=lista&chave=CHAVE                                      (só o PC)
 */
const NOME = 'Trampo com IA';
const SITE = 'https://arthurpenedo.github.io/vagas-ia-hub/';
const ABA = 'Inscritos';
const COLUNAS = ['email', 'status', 'token', 'areas', 'pedido_em', 'confirmado_em', 'saiu_em', 'origem'];

/** Rode UMA vez pelo editor (botão Executar): cria a planilha e mostra a chave que vai para o PC. */
function configurar() {
  planilha_();
  Logger.log('Planilha: ' + SpreadsheetApp.openById(prop_('PLANILHA')).getUrl());
  Logger.log('Chave para o PC: ' + chave_());
}

function doPost(e) {
  const p = (e && e.parameter) || {};
  if (p.acao === 'sair') return sair_(p.t, true);
  if (p.site) return json_({ ok: true });                     // campo-isca: robô preencheu
  const email = String(p.email || '').trim().toLowerCase();
  if (!/^[^\s@]{1,64}@[^\s@]{1,190}\.[a-z]{2,}$/.test(email) || p.consentimento !== 'sim') return json_({ ok: false, erro: 'dados' });
  const areas = String(p.areas || '').slice(0, 300);
  const origem = String(p.origem || '').slice(0, 40);

  const trava = LockService.getScriptLock();
  trava.waitLock(15000);
  try {
    const aba = planilha_();
    const agora = new Date();
    const linha = acharLinha_(aba, 0, email);
    let token;
    if (linha) {
      const [, status, tk, , pedido] = aba.getRange(linha, 1, 1, COLUNAS.length).getValues()[0];
      token = tk;
      if (status === 'ativo') { aba.getRange(linha, 4).setValue(areas); return json_({ ok: true }); }
      // no máximo um e-mail de confirmação a cada 10 minutos para o mesmo endereço (evita usar o site para spam)
      if (status === 'pendente' && pedido && agora - new Date(pedido) < 10 * 60 * 1000) return json_({ ok: true });
      aba.getRange(linha, 2, 1, 4).setValues([['pendente', token, areas, agora]]);
    } else {
      token = Utilities.getUuid().replace(/-/g, '');
      aba.appendRow([email, 'pendente', token, areas, agora, '', '', origem]);
    }
    if (MailApp.getRemainingDailyQuota() < 1) return json_({ ok: false, erro: 'cota' });
    const link = ScriptApp.getService().getUrl() + '?acao=confirmar&t=' + token;
    MailApp.sendEmail({
      to: email,
      name: NOME,
      subject: 'Confirme para receber as vagas novas do Trampo com IA',
      body: 'Oi! Para começar a receber as vagas novas de treinamento de IA, confirme seu e-mail neste link:\n' + link +
            '\n\nSe não foi você que pediu, é só ignorar este e-mail.',
      htmlBody: '<div style="font-family:Segoe UI,Arial,sans-serif;font-size:15px;color:#24223a;max-width:520px">' +
        '<p style="font-size:20px;font-weight:800">✦ Trampo <span style="color:#8a87a6">com IA</span></p>' +
        '<p>Oi! Falta só um clique para você receber as vagas novas de treinamento de IA, remotas e pagas em dólar.</p>' +
        '<p><a href="' + link + '" style="display:inline-block;background:#6a7cf6;color:#fff;text-decoration:none;font-weight:600;padding:11px 20px;border-radius:10px">Confirmar meu e-mail</a></p>' +
        '<p style="font-size:13px;color:#8a87a6">Se não foi você que pediu, é só ignorar este e-mail: sem a confirmação, nada é enviado.</p></div>',
    });
    return json_({ ok: true });
  } finally {
    trava.releaseLock();
  }
}

function doGet(e) {
  const p = (e && e.parameter) || {};
  if (p.acao === 'lista') {
    if (!p.chave || p.chave !== chave_()) return json_({ erro: 'chave' });
    limparPendentes_();
    const linhas = planilha_().getDataRange().getValues().slice(1);
    return json_({ inscritos: linhas.filter((l) => l[1] === 'ativo').map((l) => ({ email: l[0], token: l[2], areas: l[3] })) });
  }
  // confirmar e sair mostram uma página com botão: assim o antivírus de e-mail, que abre os links sozinho, não confirma nem descadastra ninguém
  if (p.acao === 'confirmar' || p.acao === 'sair') return paginaBotao_(p.acao, String(p.t || '').replace(/[^0-9a-f]/g, '').slice(0, 32));
  return pagina_('Trampo com IA', '<p>Vagas remotas para treinar IA, em português.</p>');
}

/** Chamado pelo botão das páginas de confirmar e sair (google.script.run). */
function executar(acao, token) {
  if (acao === 'confirmar') return confirmar_(token);
  if (acao === 'sair') { sair_(token, false); return 'Pronto: você não vai mais receber nossos e-mails. Se mudar de ideia, é só se inscrever de novo no site.'; }
  return 'Ação inválida.';
}

function confirmar_(token) {
  if (!/^[0-9a-f]{32}$/.test(token)) return 'Link inválido. Faça a inscrição de novo no site.';
  const aba = planilha_();
  const linha = acharLinha_(aba, 2, token);
  if (!linha) return 'Link inválido ou antigo. Faça a inscrição de novo no site.';
  aba.getRange(linha, 2).setValue('ativo');
  aba.getRange(linha, 6).setValue(new Date());
  return 'Inscrição confirmada! A partir de amanhã você recebe as vagas novas no seu e-mail.';
}

function sair_(token, comoJson) {
  token = String(token || '');
  if (/^[0-9a-f]{32}$/.test(token)) {
    const aba = planilha_();
    const linha = acharLinha_(aba, 2, token);
    if (linha) { aba.getRange(linha, 2).setValue('saiu'); aba.getRange(linha, 7).setValue(new Date()); }
  }
  return comoJson ? json_({ ok: true }) : null;
}

/** Apaga pedidos de inscrição não confirmados há mais de 30 dias (promessa da página de privacidade). */
function limparPendentes_() {
  const aba = planilha_();
  const dados = aba.getDataRange().getValues();
  const limite = Date.now() - 30 * 864e5;
  for (let i = dados.length - 1; i >= 1; i--) {
    if (dados[i][1] === 'pendente' && dados[i][4] && new Date(dados[i][4]).getTime() < limite) aba.deleteRow(i + 1);
  }
}

// ---------- apoio ----------
function prop_(k) { return PropertiesService.getScriptProperties().getProperty(k); }

function chave_() {
  let k = prop_('CHAVE');
  if (!k) { k = Utilities.getUuid().replace(/-/g, '') + Utilities.getUuid().replace(/-/g, ''); PropertiesService.getScriptProperties().setProperty('CHAVE', k); }
  return k;
}

function planilha_() {
  let id = prop_('PLANILHA'), ss;
  if (id) ss = SpreadsheetApp.openById(id);
  else { ss = SpreadsheetApp.create('Trampo com IA - inscritos da newsletter (privado)'); PropertiesService.getScriptProperties().setProperty('PLANILHA', ss.getId()); }
  let aba = ss.getSheetByName(ABA);
  if (!aba) { aba = ss.getSheets()[0]; aba.setName(ABA); aba.getRange(1, 1, 1, COLUNAS.length).setValues([COLUNAS]); aba.setFrozenRows(1); }
  return aba;
}

function acharLinha_(aba, coluna, valor) {
  const n = aba.getLastRow();
  if (n < 2) return 0;
  const col = aba.getRange(2, coluna + 1, n - 1, 1).getValues();
  for (let i = 0; i < col.length; i++) if (col[i][0] === valor) return i + 2;
  return 0;
}

function json_(o) { return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON); }

function esc_(s) { return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }

function pagina_(titulo, corpo) {
  return HtmlService.createHtmlOutput(
    '<div style="font-family:Segoe UI,Arial,sans-serif;max-width:520px;margin:48px auto;padding:0 20px;color:#24223a">' +
    '<p style="font-size:22px;font-weight:800">✦ Trampo <span style="color:#8a87a6">com IA</span></p>' +
    '<h1 style="font-size:22px">' + esc_(titulo) + '</h1>' + corpo +
    '<p><a href="' + SITE + '" target="_top" style="color:#4f63e8">Voltar para as vagas</a></p></div>')
    .setTitle(titulo).addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

function paginaBotao_(acao, token) {
  const confirmar = acao === 'confirmar';
  const corpo =
    '<p id="m">' + (confirmar ? 'Clique no botão para confirmar sua inscrição.' : 'Clique no botão para parar de receber nossos e-mails.') + '</p>' +
    '<button id="b" style="font:inherit;font-weight:600;background:#6a7cf6;color:#fff;border:0;border-radius:10px;padding:11px 20px;cursor:pointer">' +
    (confirmar ? 'Confirmar inscrição' : 'Não quero mais receber') + '</button>' +
    '<script>document.getElementById("b").onclick=function(){var b=this;b.disabled=true;b.textContent="Um instante…";' +
    'google.script.run.withSuccessHandler(function(t){document.getElementById("m").textContent=t;b.remove();})' +
    '.withFailureHandler(function(){b.disabled=false;b.textContent="Tentar de novo";})' +
    '.executar(' + JSON.stringify(acao) + ',' + JSON.stringify(token) + ');};</script>';
  return pagina_(confirmar ? 'Confirmar inscrição' : 'Sair da lista', corpo);
}
