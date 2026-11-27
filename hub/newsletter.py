"""Newsletter: manda as vagas novas para quem confirmou a inscrição.

- A lista de inscritos fica numa planilha privada no Google do Arthur, cuidada pelo Apps Script em apps-script/.
  O PC só pede a lista (com a chave secreta) na hora de enviar; nenhum e-mail de inscrito fica no repositório.
- O envio sai pelo Gmail do Arthur (o mesmo login do resumo diário, senha no cofre do Windows), um e-mail por
  pessoa, com link de descadastro e o cabeçalho List-Unsubscribe.
- dados/newsletter-estado.json guarda só os ids das vagas já anunciadas, para nunca repetir uma vaga.
"""
from __future__ import annotations

import json
import smtplib
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from pathlib import Path

from .paginas import URL, e, link_indicacao, por_hora, slug, valor_txt

RAIZ = Path(__file__).resolve().parents[1]
VAGAS = RAIZ / "site" / "vagas.json"
INDIC = RAIZ / "site" / "indicacoes.json"
ESTADO = RAIZ / "dados" / "newsletter-estado.json"
CONFIG = RAIZ / "dados" / "newsletter.local.json"   # fora do git: {"endpoint": "...", "chave": "..."}
NOME = "Trampo com IA"
MAX_VAGAS = 12


# ---------- dados ----------
def ler_estado() -> dict:
    return json.loads(ESTADO.read_text(encoding="utf-8")) if ESTADO.exists() else {}


def salvar_estado(estado: dict) -> None:
    ESTADO.parent.mkdir(exist_ok=True)
    ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


def ler_config() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8")) if CONFIG.exists() else {}


def buscar_inscritos(cfg: dict) -> list[dict]:
    url = cfg["endpoint"] + "?" + urllib.parse.urlencode({"acao": "lista", "chave": cfg["chave"]})
    with urllib.request.urlopen(url, timeout=60) as r:
        dados = json.loads(r.read().decode("utf-8"))
    if "inscritos" not in dados:
        raise RuntimeError(f"o Apps Script recusou a lista: {dados}")
    return dados["inscritos"]


def novas_vagas(vagas: list[dict], estado: dict, hoje: date | None = None) -> list[dict]:
    """Vagas ainda não anunciadas que não são fechadas para o Brasil.
    Na primeira rodada (sem estado) só contam as publicadas nos últimos 2 dias, para não despejar o site inteiro."""
    hoje = hoje or date.today()
    vistas = set(estado.get("anunciadas", []))
    corte = (hoje - timedelta(days=2)).isoformat()
    saida = []
    for v in vagas:
        if v.get("dup") or v.get("brasil") == "nao" or v["id"] in vistas:
            continue
        if not estado and (v.get("publicada") or "") < corte:
            continue
        saida.append(v)
    # quem aceita o Brasil e mostra o valor vem primeiro; depois as mais bem pagas
    return sorted(saida, key=lambda v: (v.get("brasil") == "sim", por_hora(v) > 0, por_hora(v)), reverse=True)


def para_inscrito(novas: list[dict], areas: str) -> list[dict]:
    escolhidas = [a for a in (areas or "").split("|") if a]
    return [v for v in novas if not escolhidas or v.get("area") in escolhidas]


# ---------- e-mail ----------
def link_sair(cfg: dict, token: str) -> str:
    return cfg["endpoint"] + "?" + urllib.parse.urlencode({"acao": "sair", "t": token})


def montar(vagas: list[dict], indic: dict, rotulos: dict, sair: str, total: int) -> tuple[str, str, str]:
    """Devolve (assunto, texto, html)."""
    mostrar = vagas[:MAX_VAGAS]
    n = len(vagas)
    melhor = next((valor_txt(v) for v in mostrar if v.get("unidade") == "hora" and valor_txt(v)), "")
    assunto = f"{n} {'vaga nova' if n == 1 else 'vagas novas'} para treinar IA" + (f" · até {melhor}" if melhor else "")
    utm = "utm_source=newsletter&utm_medium=email"

    linhas_txt, cartoes = [], []
    for v in mostrar:
        titulo = v.get("tituloPt") or v["titulo"]
        rot = rotulos.get(v["plataforma"], v["plataforma"])
        val = valor_txt(v)
        pagina = f"{URL}vaga/{slug(v)}.html?{utm}"
        candidatar = link_indicacao(v, indic)
        selo = "Aceita o Brasil" if v.get("brasil") == "sim" else "País não informado"
        linhas_txt.append(f"- {titulo} ({rot}{', ' + val if val else ''}) · {selo}\n  Detalhes: {pagina}\n  Candidatar: {candidatar}")
        resumo = (v.get("resumoPt") or v.get("resumo") or "")[:180]
        cartoes.append(f"""
<tr><td style="padding:0 0 14px">
 <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#ffffff;border:1px solid #e6e1f7;border-radius:14px">
  <tr><td style="padding:16px 18px">
   <div style="font-size:12px;color:#8a87a6">{e(rot)} · {e(v.get('area', ''))} · <span style="color:{'#17714f' if v.get('brasil') == 'sim' else '#8a87a6'}">{selo}</span></div>
   <div style="font-size:17px;font-weight:700;color:#24223a;margin:4px 0 2px"><a href="{e(pagina)}" style="color:#24223a;text-decoration:none">{e(titulo)}</a></div>
   {f'<div style="font-size:16px;font-weight:700;color:#d4508a;margin:2px 0 6px">{e(val)}</div>' if val else ''}
   {f'<div style="font-size:14px;color:#5d5a78;line-height:1.45;margin:4px 0 10px">{e(resumo)}{"…" if len(v.get("resumoPt") or v.get("resumo") or "") > 180 else ""}</div>' if resumo else ''}
   <a href="{e(candidatar)}" style="display:inline-block;background:#6a7cf6;color:#ffffff;text-decoration:none;font-weight:600;font-size:14px;padding:9px 16px;border-radius:10px">Ver vaga e candidatar</a>
   <a href="{e(pagina)}" style="font-size:13px;color:#4f63e8;margin-left:12px">Detalhes em português</a>
  </td></tr>
 </table>
</td></tr>""")

    resto = n - len(mostrar)
    site = f"{URL}?{utm}#vagas"
    texto = (f"Oi! Estas são as vagas novas de hoje no {NOME}:\n\n" + "\n\n".join(linhas_txt)
             + (f"\n\nE mais {resto} no site: {site}" if resto > 0 else f"\n\nTodas as {total} vagas abertas: {site}")
             + "\n\nA candidatura, a seleção e o pagamento acontecem no site de cada plataforma. Alguns links são de indicação:"
             " você não paga nada e, se for aprovado e trabalhar, a plataforma paga um bônus que mantém o site no ar."
             f"\n\nNão quer mais receber? {sair}\n")
    html = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"></head>
<body style="margin:0;background:#f3efff;font-family:Segoe UI,Helvetica,Arial,sans-serif">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f3efff"><tr><td align="center" style="padding:24px 12px">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:600px">
 <tr><td style="padding:0 0 16px">
  <div style="font-size:20px;font-weight:800;color:#24223a">✦ Trampo <span style="color:#8a87a6">com IA</span></div>
  <div style="font-size:15px;color:#5d5a78;margin-top:6px">{n} {'vaga nova' if n == 1 else 'vagas novas'} hoje, remotas e pagas em dólar. As que aceitam o Brasil vêm primeiro.</div>
 </td></tr>
 {''.join(cartoes)}
 <tr><td style="padding:4px 0 18px" align="center">
  <a href="{e(site)}" style="display:inline-block;background:#ffffff;border:1px solid #d6cff2;color:#24223a;text-decoration:none;font-weight:600;font-size:14px;padding:10px 18px;border-radius:10px">{f'Ver mais {resto} vagas novas no site' if resto > 0 else f'Ver todas as {total} vagas abertas'}</a>
 </td></tr>
 <tr><td style="font-size:12px;color:#8a87a6;line-height:1.5;padding:0 4px">
  Somos um guia independente: a candidatura, a seleção e o pagamento acontecem no site de cada plataforma.
  Alguns links são de indicação; você não paga nada e, se for aprovado e trabalhar, a plataforma paga um bônus que mantém o site no ar.
  O resumo das vagas é traduzido automaticamente.<br><br>
  Você recebe este e-mail porque se inscreveu em {e(URL)}. <a href="{e(sair)}" style="color:#5d5a78">Não quero mais receber</a>.
 </td></tr>
</table></td></tr></table></body></html>"""
    return assunto, texto, html


def mensagem(remetente: str, para: str, assunto: str, texto: str, html: str, sair: str) -> EmailMessage:
    m = EmailMessage()
    m["From"] = formataddr((NOME, remetente))
    m["To"] = para
    m["Subject"] = assunto
    m["Message-ID"] = make_msgid(domain=remetente.split("@")[-1])
    m["List-Unsubscribe"] = f"<{sair}>"
    m["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    m.set_content(texto)
    m.add_alternative(html, subtype="html")
    return m


def login_gmail() -> tuple[str, str]:
    from cerebro.carreira import USUARIO, senha_gmail  # mesmo login do resumo diário
    return USUARIO, senha_gmail(USUARIO)


# ---------- rodada ----------
def rodar(simular: bool = False, teste: str | None = None, enviar=None, inscritos: list[dict] | None = None) -> str:
    cfg = ler_config()
    if not cfg.get("endpoint") or not cfg.get("chave"):
        return "newsletter: ainda não configurada (ver apps-script/LEIA.md)"
    dados = json.loads(VAGAS.read_text(encoding="utf-8"))
    indic = json.loads(INDIC.read_text(encoding="utf-8"))
    rotulos = dados.get("plataformas", {})
    abertas = [v for v in dados["vagas"] if not v.get("dup")]
    estado = ler_estado()
    hoje = date.today().isoformat()

    if not teste and estado.get("ultimoEnvio") == hoje:
        return "newsletter: já enviada hoje"
    novas = novas_vagas(dados["vagas"], estado)
    if not novas:
        if not simular and not teste:
            estado.update(anunciadas=sorted(v["id"] for v in dados["vagas"]))
            salvar_estado(estado)
        return "newsletter: nenhuma vaga nova para anunciar"

    if teste:
        inscritos = [{"email": teste, "token": "teste", "areas": ""}]
    elif inscritos is None:
        inscritos = buscar_inscritos(cfg)

    envios = []
    for p in inscritos:
        dele = para_inscrito(novas, p.get("areas", ""))
        if not dele:
            continue
        sair = link_sair(cfg, p["token"])
        assunto, texto, html = montar(dele, indic, rotulos, sair, len(abertas))
        envios.append((p["email"], assunto, texto, html, sair))

    if simular:
        exemplo = envios[0][1] if envios else "-"
        return f"newsletter (simulação): {len(novas)} vagas novas, {len(envios)} de {len(inscritos)} inscritos receberiam. Assunto: {exemplo}"

    remetente, senha = ("", "") if enviar else login_gmail()
    if not enviar and not senha:
        return "newsletter: sem a senha do Gmail (rode `cerebro emails --configurar`)"
    enviados, falhas = 0, 0
    smtp = None
    try:
        if not enviar:
            smtp = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60)
            smtp.login(remetente, senha)
            enviar = smtp.send_message
        for para, assunto, texto, html, sair in envios:
            try:
                enviar(mensagem(remetente or "teste@exemplo.com", para, assunto, texto, html, sair))
                enviados += 1
                if smtp:
                    time.sleep(1.5)  # devagar: o Gmail desconfia de rajadas
            except smtplib.SMTPRecipientsRefused:
                falhas += 1
    finally:
        if smtp:
            smtp.quit()

    if not teste:
        estado.update(anunciadas=sorted(v["id"] for v in dados["vagas"]), ultimoEnvio=hoje)
        estado.setdefault("historico", []).append(
            {"data": hoje, "hora": datetime.now().strftime("%H:%M"), "vagas": len(novas), "enviados": enviados, "falhas": falhas})
        estado["historico"] = estado["historico"][-60:]
        salvar_estado(estado)
    return f"newsletter: {len(novas)} vagas novas, {enviados} e-mails enviados, {falhas} falhas"
