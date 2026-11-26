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
    sitemap: str
    padrao: str                      # regex que separa as URLs de vaga no sitemap
    id_da_url: Callable[[str], str]


PLATAFORMAS = [
    Plataforma("mercor", "Mercor", "https://work.mercor.com/sitemap.xml", r"/jobs/list_[A-Za-z0-9_-]+",
               lambda u: re.search(r"(list_[A-Za-z0-9_-]+)", u).group(1)),
    Plataforma("micro1", "micro1", "https://jobs.micro1.ai/sitemap.xml", r"/post/[0-9a-f-]{36}$",
               lambda u: u.rstrip("/").rsplit("/", 1)[1]),
]


def hoje() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def coletar(atuais: dict[str, dict], plataformas=PLATAFORMAS, baixar=baixar, pausa: float = 1.0,
            maximo_novas: int = 400, log=print) -> tuple[dict[str, dict], dict]:
    """Atualiza o dicionário {id: vaga}. Devolve (vagas, resumo da rodada)."""
    vagas = dict(atuais)
    resumo = {"novas": [], "removidas": [], "erros": 0}
    d = hoje()
    for p in plataformas:
        try:
            urls = urls_do_sitemap(baixar(p.sitemap), p.padrao)
        except Exception as e:  # plataforma fora do ar: mantém o que já temos
            log(f"[{p.nome}] sitemap falhou: {e}")
            resumo["erros"] += 1
            continue
        ids_vivos = {f"{p.nome}:{p.id_da_url(u)}": u for u in urls}
        for vid in [k for k, v in vagas.items() if v["plataforma"] == p.nome and k not in ids_vivos]:
            resumo["removidas"].append(vid)
            del vagas[vid]
        novas = [(vid, u) for vid, u in ids_vivos.items() if vid not in vagas][:maximo_novas]
        log(f"[{p.nome}] {len(urls)} no sitemap, {len(novas)} novas")
        for vid, u in novas:
            try:
                jp = job_posting(baixar(u))
            except Exception:
                resumo["erros"] += 1
                continue
            finally:
                time.sleep(pausa)
            if not jp:
                continue
            v = normalizar(jp, u, p.nome, vid.split(":", 1)[1])
            v["vistaEm"] = d
            vagas[vid] = v
            resumo["novas"].append(vid)
    for vid in [k for k, v in vagas.items() if v.get("expira") and v["expira"] < d]:
        resumo["removidas"].append(vid)
        del vagas[vid]
    return vagas, resumo
