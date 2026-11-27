"""Gera as páginas estáticas que o site precisa além da home: uma página por vaga, o sitemap e o robots.txt.

Roda na publicação (GitHub Actions), a partir de site/vagas.json; nada disso fica no repositório.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import unicodedata
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SITE = RAIZ / "site"
URL = "https://arthurpenedo.github.io/vagas-ia-hub/"
GUIAS = {"mercor": "guias/mercor.html", "micro1": "guias/micro1.html"}
HORAS = {"hora": 1, "dia": 8, "semana": 40, "mês": 173, "ano": 2080}

ICONE = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Cdefs%3E%3ClinearGradient id='g' "
         "x1='0' y1='0' x2='1' y2='1'%3E%3Cstop stop-color='%233b82f6'/%3E%3Cstop offset='1' stop-color='%238b5cf6'/%3E%3C/linearGradient%3E"
         "%3C/defs%3E%3Crect width='32' height='32' rx='9' fill='url(%23g)'/%3E%3Cpath d='M16 6l2.6 6.4L25 15l-6.4 2.6L16 24l-2.6-6.4L7 15l6.4-2.6z' "
         "fill='white'/%3E%3C/svg%3E")


def e(s) -> str:
    return html.escape(str(s or ""), quote=True)


def slug(v: dict) -> str:
    """Endereço estável da vaga: título original sem acento + 8 caracteres do id (a tradução pode mudar; isto não)."""
    base = unicodedata.normalize("NFKD", v["titulo"]).encode("ascii", "ignore").decode().lower()
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")[:60].rstrip("-") or "vaga"
    return f"{base}-{hashlib.sha1(v['id'].encode()).hexdigest()[:8]}"


def link_indicacao(v: dict, indic: dict) -> str:
    cfg = indic.get(v["plataforma"]) or {}
    if not cfg.get("codigo"):
        return v["url"]
    from urllib.parse import quote
    return (cfg["modelo"].replace("{url}", v["url"]).replace("{sep}", "&" if "?" in v["url"] else "?")
            .replace("{codigo}", quote(cfg["codigo"], safe="")))


def por_hora(v: dict) -> float:
    x = v.get("valorMax") if v.get("valorMax") is not None else v.get("valorMin")
    return -1 if x is None or v.get("unidade") not in HORAS else x / HORAS[v["unidade"]]


def valor_txt(v: dict) -> str:
    mn, mx = v.get("valorMin"), v.get("valorMax")
    if mn is None and mx is None:
        return ""
    moeda = "US$ " if v.get("moeda") == "USD" else (f"{v['moeda']} " if v.get("moeda") else "")
    n = lambda x: f"{x:,.0f}".replace(",", ".")
    faixa = n(mx) if mn is None else (f"{n(mn)}–{n(mx)}" if mx and mx != mn else n(mn))
    unid = "/h" if v.get("unidade") == "hora" else (f"/{v['unidade']}" if v.get("unidade") else "")
    return f"{'até ' if mn is None else ''}{moeda}{faixa}{unid}"


def selo_pais(v: dict) -> str:
    if v.get("brasil") == "sim":
        return '<span class="selo br">Aceita o Brasil</span>'
    if v.get("brasil") == "nao":
        return '<span class="selo fora">Fechada para o Brasil</span>'
    return '<span class="selo">País não informado</span>'


def topo(raiz: str) -> str:
    return f"""<header class="topo"><div class="envolve">
  <a class="logo" href="{raiz}"><span class="logo-marca"><svg viewBox="0 0 24 24" fill="#fff" aria-hidden="true"><path d="M12 2l2.6 6.4L21 11l-6.4 2.6L12 20l-2.6-6.4L3 11l6.4-2.6z"/></svg></span>Trampo<span>com IA</span></a>
  <nav class="menu"><a href="{raiz}#vagas">Vagas</a><a href="{raiz}guias/">Guias</a><a href="{raiz}como-funciona.html">Sobre</a><a class="news-link" href="#novidades" hidden>Receber vagas</a><a class="cta" href="{raiz}#vagas">Ver vagas</a></nav>
</div></header>"""


def caixa_newsletter(raiz: str, origem: str) -> str:
    return f"""<section class="news vidro" id="novidades" hidden>
  <div class="news-texto"><h2>Receba as vagas novas no seu e-mail</h2>
    <p>Um e-mail por dia, só quando aparecem vagas novas que aceitam o Brasil. Sai quando quiser, com um clique.</p></div>
  <form class="news-form" data-origem="{e(origem)}" novalidate>
    <div class="news-linha"><input type="email" name="email" placeholder="seu@email.com" autocomplete="email" required aria-label="Seu e-mail">
      <button class="botao" type="submit">Quero receber</button></div>
    <input class="news-isca" type="text" name="site" tabindex="-1" autocomplete="off" aria-hidden="true">
    <details class="news-areas"><summary>Só de algumas áreas? (opcional)</summary><div class="news-chips"></div></details>
    <label class="news-ok"><input type="checkbox" name="consentimento" value="sim" required> Aceito receber vagas por e-mail e li a <a href="{raiz}privacidade.html">política de privacidade</a>.</label>
    <p class="news-msg" role="status" aria-live="polite"></p>
  </form>
</section>"""


def rodape(raiz: str) -> str:
    return f"""<footer><div class="envolve">
  <p><b>Somos um guia independente.</b> Não somos a Mercor, a micro1 nem outra plataforma, e não contratamos ninguém:
     a candidatura, a seleção e o pagamento acontecem no site de cada empresa.</p>
  <p>Alguns links são de indicação: você não paga nada e, se for aprovado e trabalhar, a plataforma paga um bônus que mantém o site no ar.
     <a href="{raiz}como-funciona.html">Saiba mais</a> · <a href="{raiz}privacidade.html">Privacidade</a></p>
</div></footer>"""


def cabeca(titulo: str, descricao: str, raiz: str, canonica: str, extra: str = "") -> str:
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#faf8ff">
<title>{e(titulo)}</title>
<meta name="description" content="{e(descricao)}">
<link rel="canonical" href="{e(canonica)}">
<meta property="og:type" content="website">
<meta property="og:title" content="{e(titulo)}">
<meta property="og:description" content="{e(descricao)}">
<meta property="og:url" content="{e(canonica)}">
<meta property="og:image" content="https://arthurpenedo.github.io/vagas-ia-hub/og.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="{ICONE}">
<link rel="stylesheet" href="{raiz}estilo.css">
{extra}</head>"""


def pagina_vaga(v: dict, indic: dict, rotulos: dict, parecidas: list[dict]) -> str:
    raiz = "../"
    titulo = v.get("tituloPt") or v["titulo"]
    rot = rotulos.get(v["plataforma"], v["plataforma"])
    val = valor_txt(v)
    resumo_pt = v.get("resumoPt") or v.get("resumo") or ""
    desc = f"{titulo} · {rot} · {val + ' · ' if val else ''}vaga remota de treinamento de IA. {resumo_pt}"[:300]
    canonica = f"{URL}vaga/{slug(v)}.html"
    paises = v.get("paises") or []
    lista_paises = (f"<p class=\"paises\"><b>Países aceitos:</b> {e(', '.join(paises))}</p>" if paises
                    else "<p class=\"paises\">A vaga não informa os países aceitos. Confira na página oficial.</p>")
    habilidades = "".join(f'<span class="selo">{e(h)}</span>' for h in (v.get("habilidades") or [])[:14])
    guia = GUIAS.get(v["plataforma"])
    original = ""
    if v.get("resumo") and v.get("resumoPt") and v["resumo"] != v["resumoPt"]:
        original = f'<details class="original-desc"><summary>Ver o texto original, em inglês</summary><p>{e(v["resumo"])}</p></details>'
    parecidas_html = "".join(
        f'<li><a href="{slug(p)}.html">{e(p.get("tituloPt") or p["titulo"])}</a>'
        f'<small>{e(rotulos.get(p["plataforma"], p["plataforma"]))}{" · " + e(valor_txt(p)) if valor_txt(p) else ""}</small></li>'
        for p in parecidas)
    publicada = ""
    if v.get("publicada"):
        d = v["publicada"].split("-")
        publicada = f"Publicada em {d[2]}/{d[1]}/{d[0]}"
    return f"""{cabeca(f"{titulo} · {rot} · Trampo com IA", desc, raiz, canonica)}
<body>
{topo(raiz)}
<main class="pagina-texto"><div class="aurora" aria-hidden="true"><i></i><i></i><i></i></div><div class="envolve texto vaga-pagina">
  <p class="migalha"><a href="{raiz}#vagas">Vagas</a> › <a href="{raiz}?area={e(v.get("area", ""))}#vagas">{e(v.get("area", ""))}</a></p>
  <div class="vaga-topo"><span class="plat {e(v["plataforma"])}">{e(rot)}</span><span>{e(publicada)}</span></div>
  <h1>{e(titulo)}</h1>
  {f'<p class="original">Título original: <i>{e(v["titulo"])}</i></p>' if titulo != v["titulo"] else ""}
  {f'<div class="valor">{e(val)}<small>{"por hora" if v.get("unidade") == "hora" else "anunciado"}</small></div>' if val else '<div class="valor sem">Valor na página da vaga</div>'}
  <div class="meta"><span class="selo">{e(v.get("area", ""))}</span>{selo_pais(v)}</div>
  <div class="acoes grandes">
    <a class="botao" href="{e(link_indicacao(v, indic))}" target="_blank" rel="noopener sponsored">Ver vaga e candidatar
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M7 17L17 7M9 7h8v8"/></svg></a>
    <button class="botao-vidro compartilhar" type="button" data-titulo="{e(titulo)}">Compartilhar</button>
    {f'<a class="link-guia" href="{raiz}{guia}">Como passar na seleção da {e(rot)}</a>' if guia else ""}
  </div>
  <h2>Sobre a vaga</h2>
  <p>{e(resumo_pt) or "A plataforma não publicou um resumo. Veja os detalhes na página oficial."}</p>
  {original}
  {f'<h2>Habilidades pedidas</h2><div class="meta">{habilidades}</div>' if habilidades else ""}
  <h2>Quem pode se candidatar</h2>
  {lista_paises}
  <p class="aviso">A candidatura, a seleção e o pagamento acontecem no site da {e(rot)}, em inglês. O resumo foi traduzido
     automaticamente: na dúvida, vale o texto da página oficial. Nenhuma plataforma séria cobra para você se candidatar.</p>
  {caixa_newsletter(raiz, "vaga")}
  {f'<h2>Vagas parecidas</h2><ul class="lista-guias parecidas">{parecidas_html}</ul>' if parecidas_html else ""}
</div></main>
{rodape(raiz)}
<script src="{raiz}newsletter.js"></script>
<script>
document.querySelector(".compartilhar")?.addEventListener("click", async (ev) => {{
  const b = ev.currentTarget, url = location.href.split("#")[0], titulo = b.dataset.titulo;
  try {{
    if (navigator.share) await navigator.share({{ title: titulo, text: titulo + " · vaga remota de IA", url }});
    else {{ await navigator.clipboard.writeText(url); b.textContent = "Link copiado"; }}
  }} catch (_) {{}}
}});
</script>
</body>
</html>
"""


def parecidas_de(v: dict, por_area: dict[str, list[dict]], n: int = 4) -> list[dict]:
    """As mais bem pagas da mesma área, sem repetir título; quem aceita o Brasil vem antes."""
    vistos, saida = {v["titulo"].lower()}, []
    for p in por_area.get(v.get("area"), []):
        if p["id"] == v["id"] or p["titulo"].lower() in vistos:
            continue
        saida.append(p)
        vistos.add(p["titulo"].lower())
        if len(saida) == n:
            break
    return saida


def gerar(site: Path = SITE) -> int:
    dados = json.loads((site / "vagas.json").read_text(encoding="utf-8"))
    indic = json.loads((site / "indicacoes.json").read_text(encoding="utf-8"))
    rotulos = dados.get("plataformas", {})
    vagas = [v for v in dados["vagas"] if not v.get("dup")]
    por_area: dict[str, list[dict]] = {}
    for v in sorted(vagas, key=lambda x: (x.get("brasil") == "sim", por_hora(x)), reverse=True):
        por_area.setdefault(v.get("area"), []).append(v)

    pasta = site / "vaga"
    pasta.mkdir(exist_ok=True)
    for velho in pasta.glob("*.html"):
        velho.unlink()
    for v in vagas:
        (pasta / f"{slug(v)}.html").write_text(pagina_vaga(v, indic, rotulos, parecidas_de(v, por_area)), encoding="utf-8")

    hoje = date.today().isoformat()
    fixas = ["", "como-funciona.html", "guias/", "guias/geral.html", "guias/mercor.html", "guias/micro1.html", "privacidade.html"]
    urls = [f"<url><loc>{URL}{p}</loc><lastmod>{hoje}</lastmod></url>" for p in fixas]
    urls += [f"<url><loc>{URL}vaga/{slug(v)}.html</loc><lastmod>{v.get('vistaEm') or v.get('publicada') or hoje}</lastmod></url>"
             for v in vagas]
    (site / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n'
                                      '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                                      + "\n".join(urls) + "\n</urlset>\n", encoding="utf-8")
    (site / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {URL}sitemap.xml\n", encoding="utf-8")
    return len(vagas)
