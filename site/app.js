"use strict";
const $ = (id) => document.getElementById(id);
const POR_PAGINA = 30;
const GUIAS = { mercor: "guias/mercor.html", micro1: "guias/micro1.html" };
const estado = { vagas: [], plataformas: {}, indic: {}, area: "", pagina: 1 };

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const seguro = (u) => (/^https:\/\//.test(u) ? u : "#");

function linkIndicacao(v) {
  const cfg = estado.indic[v.plataforma];
  if (!cfg || !cfg.codigo) return v.url;
  return cfg.modelo
    .replace("{url}", v.url)
    .replace("{sep}", v.url.includes("?") ? "&" : "?")
    .replace("{codigo}", encodeURIComponent(cfg.codigo));
}

const HORAS = { hora: 1, dia: 8, semana: 40, "mês": 173, ano: 2080 };
const porHora = (v) => (v.valorMax ?? v.valorMin) == null || !HORAS[v.unidade] ? -1 : (v.valorMax ?? v.valorMin) / HORAS[v.unidade];

function valorTxt(v) {
  if (v.valorMin == null && v.valorMax == null) return "";
  const moeda = v.moeda === "USD" ? "US$ " : (v.moeda ? v.moeda + " " : "");
  const n = (x) => Number(x).toLocaleString("pt-BR", { maximumFractionDigits: 0 });
  const faixa = v.valorMin == null ? n(v.valorMax)
    : v.valorMax && v.valorMax !== v.valorMin ? `${n(v.valorMin)}–${n(v.valorMax)}` : n(v.valorMin);
  return `${v.valorMin == null ? "até " : ""}${moeda}${faixa}${v.unidade ? "/" + (v.unidade === "hora" ? "h" : v.unidade) : ""}`;
}

function quando(d) {
  if (!d) return "";
  const dias = Math.floor((Date.now() - new Date(d + "T12:00:00")) / 864e5);
  if (dias <= 0) return "hoje";
  if (dias === 1) return "ontem";
  if (dias < 30) return `há ${dias} dias`;
  return new Date(d + "T12:00:00").toLocaleDateString("pt-BR");
}

function seloPais(v) {
  if (v.brasil === "sim") return `<span class="selo br">Aceita o Brasil</span>`;
  if (v.brasil === "nao") {
    const p = v.paises.slice(0, 3).join(", ") + (v.paises.length > 3 ? ` +${v.paises.length - 3}` : "");
    return `<span class="selo fora" title="${esc(v.paises.join(", "))}">Só ${esc(p)}</span>`;
  }
  return `<span class="selo">País não informado</span>`;
}

function cartao(v) {
  const val = valorTxt(v);
  const rot = estado.plataformas[v.plataforma] || v.plataforma;
  const unid = v.unidade === "hora" ? "por hora" : "anunciado";
  return `<article class="vaga">
    <div class="vaga-topo"><span class="plat ${esc(v.plataforma)}">${esc(rot)}</span>${v.publicada ? `<span>${quando(v.publicada)}</span>` : ""}</div>
    <h3>${esc(v.titulo)}</h3>
    ${val ? `<div class="valor">${esc(val)}<small>${unid}</small></div>` : `<div class="valor sem">Valor na página da vaga</div>`}
    <div class="meta"><span class="selo">${esc(v.area)}</span>${seloPais(v)}</div>
    ${v.resumo ? `<p class="resumo">${esc(v.resumo)}</p>` : ""}
    <div class="acoes">
      <a class="botao" href="${esc(seguro(linkIndicacao(v)))}" target="_blank" rel="noopener sponsored">Candidatar
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M7 17L17 7M9 7h8v8"/></svg></a>
      ${GUIAS[v.plataforma] ? `<a class="link-guia" href="${GUIAS[v.plataforma]}">Guia da ${esc(rot)}</a>` : ""}
    </div>
  </article>`;
}

// Em destaque: aceita o Brasil e mostra o valor vem primeiro; depois, as mais recentes.
const destaque = (v) => (v.brasil === "sim" ? 2 : 0) + (porHora(v) > 0 ? 1 : 0);

function vitrine() {
  // três vagas por hora, de áreas diferentes, das mais bem pagas; as que aceitam o Brasil vêm primeiro
  const porValor = estado.vagas.filter((v) => v.unidade === "hora" && porHora(v) > 0)
    .sort((a, b) => (b.brasil === "sim") - (a.brasil === "sim") || porHora(b) - porHora(a));
  const escolha = [], areas = new Set(), titulos = new Set();
  for (const v of porValor) {
    if (areas.has(v.area) || titulos.has(v.titulo)) continue;
    escolha.push(v); areas.add(v.area); titulos.add(v.titulo);
    if (escolha.length === 3) break;
  }
  $("vitrine").innerHTML = escolha.map(cartao).join("");
}

function filtradas() {
  const q = $("busca").value.trim().toLowerCase();
  const plat = $("plataforma").value;
  const soBr = $("so-br").checked;
  let l = estado.vagas.filter((v) =>
    (!estado.area || v.area === estado.area) &&
    (!plat || v.plataforma === plat) &&
    (!soBr || v.brasil !== "nao") &&
    (!q || (v.titulo + " " + v.resumo + " " + v.habilidades.join(" ") + " " + v.area).toLowerCase().includes(q)));
  const ordem = $("ordem").value;
  if (ordem === "valor") l = l.slice().sort((a, b) => porHora(b) - porHora(a));
  if (ordem === "destaque") l = l.slice().sort((a, b) => destaque(b) - destaque(a) || (b.publicada || "").localeCompare(a.publicada || ""));
  return l;
}

function desenhar() {
  const l = filtradas();
  const mostrar = l.slice(0, estado.pagina * POR_PAGINA);
  $("lista").innerHTML = mostrar.map(cartao).join("");
  $("resultado").textContent = l.length ? `${l.length.toLocaleString("pt-BR")} ${l.length === 1 ? "vaga" : "vagas"}` : "";
  if (!l.length) $("lista").innerHTML = `<div class="vazio vidro">Nenhuma vaga com esses filtros. Tente tirar algum ou buscar outra palavra.</div>`;
  $("mais").hidden = mostrar.length >= l.length;
}

function chips() {
  const cont = {};
  estado.vagas.forEach((v) => (cont[v.area] = (cont[v.area] || 0) + 1));
  const areas = Object.keys(cont).sort((a, b) => (a === "Outras áreas") - (b === "Outras áreas") || cont[b] - cont[a]);
  $("areas").innerHTML = [["", "Todas"], ...areas.map((a) => [a, `${a} · ${cont[a]}`])]
    .map(([k, t]) => `<button class="chip" data-area="${esc(k)}" aria-pressed="${k === estado.area}">${esc(t)}</button>`).join("");
}

function numeros() {
  const br = estado.vagas.filter((v) => v.brasil === "sim").length;
  const hora = estado.vagas.filter((v) => v.unidade === "hora" && v.valorMin != null).map((v) => (v.valorMin + (v.valorMax ?? v.valorMin)) / 2).sort((a, b) => a - b);
  $("n-total").textContent = estado.vagas.length.toLocaleString("pt-BR");
  $("n-br").textContent = br.toLocaleString("pt-BR");
  $("n-mediana").textContent = hora.length ? `US$ ${Math.round(hora[Math.floor(hora.length / 2)])}` : "–";
  $("h-total").textContent = estado.vagas.length.toLocaleString("pt-BR");
  const areas = [...new Set(estado.vagas.map((v) => v.area))].filter((a) => a !== "Outras áreas");
  const itens = areas.map((a) => `<span>${esc(a)}</span>`).join("");
  const metade = itens + itens + itens;
  $("faixa").innerHTML = metade + metade;  // a animação anda meia faixa: as duas metades iguais escondem a emenda
}

async function iniciar() {
  try {
    const [dados, indic] = await Promise.all([
      fetch("vagas.json", { cache: "no-cache" }).then((r) => r.json()),
      fetch("indicacoes.json", { cache: "no-cache" }).then((r) => r.json()).catch(() => ({})),
    ]);
    estado.vagas = (dados.vagas || []).filter((v) => !v.dup);
    estado.plataformas = dados.plataformas || {};
    estado.indic = indic;
    for (const [k, rot] of Object.entries(estado.plataformas)) $("plataforma").insertAdjacentHTML("beforeend", `<option value="${esc(k)}">${esc(rot)}</option>`);
    const dia = dados.atualizado ? dados.atualizado.split(" ")[0].split("-").reverse().join("/") : "";
    $("atualizado").textContent = dia ? `Vagas atualizadas em ${dia}.` : "";
    if (dia) $("h-data").textContent = dia === new Date().toLocaleDateString("pt-BR") ? "hoje" : `em ${dia.slice(0, 5)}`;
    const u = new URLSearchParams(location.search);
    if (u.get("q")) $("busca").value = u.get("q");
    if (u.get("area")) estado.area = u.get("area");
    if (u.get("plataforma")) $("plataforma").value = u.get("plataforma");
    numeros(); chips(); vitrine(); desenhar();
  } catch (e) {
    $("resultado").textContent = "Não consegui carregar as vagas agora. Tente recarregar a página.";
  }
}

let t;
$("busca").addEventListener("input", () => { clearTimeout(t); t = setTimeout(() => { estado.pagina = 1; desenhar(); }, 150); });
["plataforma", "ordem", "so-br"].forEach((id) => $(id).addEventListener("change", () => { estado.pagina = 1; desenhar(); }));
$("areas").addEventListener("click", (e) => {
  const b = e.target.closest("[data-area]"); if (!b) return;
  estado.area = b.dataset.area; estado.pagina = 1; chips(); desenhar();
});
$("mais").addEventListener("click", () => { estado.pagina++; desenhar(); });
iniciar();
