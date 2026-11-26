"""Coleta vagas públicas das plataformas de treinamento de IA.

Cada plataforma publica um sitemap com as páginas de vaga, e cada página traz um bloco
JSON-LD `JobPosting` (o mesmo que o Google lê). A coleta usa só isso: nada de API interna,
login ou página bloqueada no robots.txt. Uma requisição por segundo, e só as vagas novas
são baixadas; as que saíram do sitemap ou venceram são retiradas.
"""
from __future__ import annotations

import html
import json
import re
import time
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from .classificar import abre_brasil, area_da_vaga, paises_da_vaga

AGENTE = "Mozilla/5.0 (compatible; hub-vagas-ia/0.1; coleta de vagas publicas)"


def baixar(url: str, tentativas: int = 2) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": AGENTE, "Accept-Language": "en"})
    for n in range(tentativas):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except Exception:
            if n == tentativas - 1:
                raise
            time.sleep(3)
    return ""


def urls_do_sitemap(xml: str, padrao: str) -> list[str]:
    return sorted({u for u in re.findall(r"<loc>([^<]+)</loc>", xml) if re.search(padrao, u)})


# ---------- extração do JobPosting ----------

def _jsonld_scripts(pagina: str) -> list[dict]:
    """Blocos <script type="application/ld+json"> comuns (Mercor)."""
    out = []
    for bloco in re.findall(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', pagina, re.S):
        try:
            out.append(json.loads(bloco))
        except json.JSONDecodeError:
            continue
    return out


def _jsonld_rsc(pagina: str) -> list[dict]:
    """JSON-LD que o Next.js (app router) manda dentro de self.__next_f.push (micro1)."""
    partes = re.findall(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)', pagina)
    if not partes:
        return []
    txt = "".join(json.loads('"' + p + '"') for p in partes)
    out, pos = [], 0
    while (i := txt.find('"@type":"JobPosting"', pos)) != -1:
        ini = txt.rfind("{", 0, i)
        try:
            d, fim = json.JSONDecoder().raw_decode(txt[ini:])
            out.append(d)
            pos = ini + fim
        except json.JSONDecodeError:
            pos = i + 1
    return out


def job_posting(pagina: str) -> dict | None:
    for d in _jsonld_scripts(pagina) + _jsonld_rsc(pagina):
        if isinstance(d, dict) and d.get("@type") == "JobPosting":
            return d
    return None


def texto_limpo(desc: str, limite: int = 320) -> str:
    t = re.sub(r"<[^>]+>", " ", desc or "")
    t = re.sub(r"\s+", " ", html.unescape(t)).strip()
    # micro1 abre com "Role Title: X Role Type: Contractor Location: Remote": repete o card
    t = re.sub(r"^Role Title:.*?Location:\s*\S+\s*", "", t)
    return t if len(t) <= limite else t[: limite - 1].rsplit(" ", 1)[0] + "…"


def _valor(jp: dict) -> tuple[float | None, float | None, str, str]:
    bs = jp.get("baseSalary") or {}
    v = bs.get("value") or {}
    if not isinstance(v, dict):
        return None, None, "", ""
    mn, mx = v.get("minValue"), v.get("maxValue")
    if mn is None and mx is None and v.get("value") is not None:
        mn = mx = v["value"]
    unidade = {"HOUR": "hora", "DAY": "dia", "WEEK": "semana", "MONTH": "mês", "YEAR": "ano"}.get(
        str(v.get("unitText", "")).upper(), "")
    return mn, mx, bs.get("currency", ""), unidade


def normalizar(jp: dict, url: str, plataforma: str, id_: str) -> dict:
    mn, mx, moeda, unidade = _valor(jp)
    paises = paises_da_vaga(jp.get("applicantLocationRequirements"))
    titulo = html.unescape(jp.get("title", "")).strip()
    skills = jp.get("skills") or []
    if isinstance(skills, str):
        skills = [s.strip() for s in skills.split(",") if s.strip()]
    desc = jp.get("description", "")
    return {
        "id": f"{plataforma}:{id_}",
        "plataforma": plataforma,
        "titulo": titulo,
        "url": url,
        "area": area_da_vaga(titulo, " ".join(skills) + " " + texto_limpo(desc, 600)),
        "valorMin": mn,
        "valorMax": mx,
        "moeda": moeda,
        "unidade": unidade,
        "paises": paises,
        "brasil": abre_brasil(paises),
        "habilidades": skills[:6],
        "resumo": texto_limpo(desc),
        "publicada": str(jp.get("datePosted") or "")[:10],
        "expira": str(jp.get("validThrough") or "")[:10],
    }


# ---------- plataformas ----------

@dataclass
class Plataforma:
    nome: str
    rotulo: str
    sitemap: str = ""
    padrao: str = ""                 # regex que separa as URLs de vaga no sitemap
    id_da_url: Callable[[str], str] = lambda u: u.rstrip("/").rsplit("/", 1)[1]
    listar: Callable | None = None   # (baixar) -> URLs de vaga, quando não há sitemap de vagas
    extrair: Callable | None = None  # (pagina, url, nome, id) -> vaga normalizada ou None
    lista_completa: bool = True      # False: a listagem mostra só as mais recentes, então sumir dela não fecha a vaga

    def urls(self, baixar) -> list[str]:
        if self.listar:
            return self.listar(baixar)
        return urls_do_sitemap(baixar(self.sitemap), self.padrao)

    def vaga(self, pagina: str, url: str, id_: str) -> dict | None:
        if self.extrair:
            return self.extrair(pagina, url, self.nome, id_)
        jp = job_posting(pagina)
        return normalizar(jp, url, self.nome, id_) if jp else None


def _meta(pagina: str, nome: str) -> str:
    m = re.search(r'<meta[^>]+(?:name|property)="' + re.escape(nome) + r'"[^>]+content="([^"]*)"', pagina)
    return html.unescape(m.group(1)).strip() if m else ""


def _next_data(pagina: str) -> dict:
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', pagina, re.S)
    return json.loads(m.group(1)).get("props", {}).get("pageProps", {}) if m else {}


# Alignerr: a página pública /jobs traz as 60 vagas mais recentes; a página de cada vaga traz os dados completos.
ALIGNERR = "https://www.alignerr.com"


def listar_alignerr(baixar) -> list[str]:
    jobs = _next_data(baixar(ALIGNERR + "/en/jobs")).get("initialJobs", [])
    return [ALIGNERR + j["applyUrl"] for j in jobs if str(j.get("applyUrl", "")).startswith("/jobs/")]


def extrair_alignerr(pagina: str, url: str, nome: str, id_: str) -> dict | None:
    j = _next_data(pagina).get("job")
    if not j or not j.get("isActive", True):
        return None
    paises = paises_da_vaga([j["countryCode"]] if j.get("countryCode") else
                            ([] if str(j.get("location", "")).lower() in ("", "remote") else [j["location"]]))
    titulo = j.get("name", "").strip()
    desc = j.get("htmlLongDescription") or j.get("shortDescription") or ""
    corpo = texto_limpo(j.get("shortDescription") or desc)
    return {
        "id": f"{nome}:{id_}", "plataforma": nome, "titulo": titulo, "url": url,
        "area": area_da_vaga(titulo, texto_limpo(desc, 600)),
        "valorMin": j.get("lowerBoundHourlyRate"), "valorMax": j.get("upperBoundHourlyRate"),
        "moeda": "USD" if j.get("lowerBoundHourlyRate") is not None else "",
        "unidade": "hora" if j.get("salaryType", "HOURLY") == "HOURLY" else "",
        "paises": paises, "brasil": abre_brasil(paises), "habilidades": [],
        "resumo": corpo,
        "publicada": str(j.get("firstPostDate") or j.get("createdAt") or "")[:10], "expira": "",
    }


# Mindrift: cada "projeto" é uma página com título, descrição e "Up to $X/hr" no meta description.
def extrair_mindrift(pagina: str, url: str, nome: str, id_: str) -> dict | None:
    titulo = re.split(r"\s[–—|-]\s", _meta(pagina, "og:title") or "", maxsplit=1)[0].strip()
    desc = _meta(pagina, "description") or _meta(pagina, "og:description")
    if not titulo:
        return None
    m = re.search(r"\$\s?(\d+(?:\.\d+)?)\s?(?:/|per\s)\s?(?:hr|hour)", desc + " " + pagina[:200000], re.I)
    ate = float(m.group(1)) if m else None
    return {
        "id": f"{nome}:{id_}", "plataforma": nome, "titulo": titulo, "url": url,
        "area": area_da_vaga(titulo, desc), "valorMin": None, "valorMax": ate,
        "moeda": "USD" if ate else "", "unidade": "hora" if ate else "",
        "paises": [], "brasil": "?", "habilidades": [], "resumo": desc,
        "publicada": "", "expira": "",
    }


PLATAFORMAS = [
    Plataforma("mercor", "Mercor", "https://work.mercor.com/sitemap.xml", r"/jobs/list_[A-Za-z0-9_-]+",
               lambda u: re.search(r"(list_[A-Za-z0-9_-]+)", u).group(1)),
    Plataforma("micro1", "micro1", "https://jobs.micro1.ai/sitemap.xml", r"/post/[0-9a-f-]{36}$"),
    Plataforma("alignerr", "Alignerr", listar=listar_alignerr, extrair=extrair_alignerr, lista_completa=False),
    Plataforma("mindrift", "Mindrift", "https://mindrift.ai/sitemap.xml", r"/project/[a-z0-9-]+$",
               extrair=extrair_mindrift),
]


def hoje() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _baixar_vaga(p: Plataforma, u: str, vid: str, baixar, pausa: float):
    """Devolve a vaga, None se a página não traz vaga ativa, ou levanta erro de rede."""
    try:
        return p.vaga(baixar(u), u, vid.split(":", 1)[1])
    finally:
        time.sleep(pausa)


def coletar(atuais: dict[str, dict], plataformas=PLATAFORMAS, baixar=baixar, pausa: float = 1.0,
            maximo_novas: int = 400, reconferir: int = 30, log=print) -> tuple[dict[str, dict], dict]:
    """Atualiza o dicionário {id: vaga}. Devolve (vagas, resumo da rodada)."""
    vagas = dict(atuais)
    resumo = {"novas": [], "removidas": [], "erros": 0}
    d = hoje()

    def remover(vid):
        resumo["removidas"].append(vid)
        del vagas[vid]

    for p in plataformas:
        try:
            urls = p.urls(baixar)
        except Exception as e:  # plataforma fora do ar: mantém o que já temos
            log(f"[{p.nome}] listagem falhou: {e}")
            resumo["erros"] += 1
            continue
        ids_vivos = {f"{p.nome}:{p.id_da_url(u)}": u for u in urls}
        if p.lista_completa:
            for vid in [k for k, v in vagas.items() if v["plataforma"] == p.nome and k not in ids_vivos]:
                remover(vid)
        else:
            # a listagem só mostra as mais recentes: reconfere na página as que sumiram dela, as mais antigas primeiro
            fora = sorted((v.get("conferidaEm", ""), k) for k, v in vagas.items()
                          if v["plataforma"] == p.nome and k not in ids_vivos and v.get("conferidaEm", "") < d)
            for _, vid in fora[:reconferir]:
                try:
                    v = _baixar_vaga(p, vagas[vid]["url"], vid, baixar, pausa)
                except Exception as e:
                    if "404" in str(e) or "410" in str(e):
                        remover(vid)
                    else:
                        resumo["erros"] += 1
                    continue
                if v is None:
                    remover(vid)
                else:
                    vagas[vid]["conferidaEm"] = d
        novas = [(vid, u) for vid, u in ids_vivos.items() if vid not in vagas][:maximo_novas]
        log(f"[{p.nome}] {len(urls)} listadas, {len(novas)} novas")
        for vid, u in novas:
            try:
                v = _baixar_vaga(p, u, vid, baixar, pausa)
            except Exception:
                resumo["erros"] += 1
                continue
            if not v:
                continue
            v["vistaEm"] = v["conferidaEm"] = d
            vagas[vid] = v
            resumo["novas"].append(vid)
    for vid in [k for k, v in vagas.items() if v.get("expira") and v["expira"] < d]:
        remover(vid)
    return vagas, resumo
