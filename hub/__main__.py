"""python -m hub coletar  → atualiza site/vagas.json e escreve o log da rodada."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from .classificar import abre_brasil, area_da_vaga, paises_da_vaga
from .coleta import PLATAFORMAS, coletar, hoje
from .paginas import slug
from .traduzir import traduzir_vagas

RAIZ = Path(__file__).resolve().parents[1]
VAGAS = RAIZ / "site" / "vagas.json"
LOG = RAIZ / "coletas.log"


def ler() -> dict[str, dict]:
    if not VAGAS.exists():
        return {}
    return {v["id"]: v for v in json.loads(VAGAS.read_text(encoding="utf-8"))["vagas"]}


def marcar_duplicatas(lista: list[dict]) -> None:
    """Algumas plataformas publicam a mesma vaga várias vezes (uma por país ou cidade). O site mostra uma só,
    com os países somados; as cópias ficam no arquivo (marcadas com dup) para a coleta não achar que são novas."""
    principal: dict[tuple, dict] = {}
    for v in lista:
        v.pop("dup", None)
        v["paises"] = list(v.get("paisesProprios", v["paises"]))  # desfaz a soma da rodada anterior
        v["paisesProprios"] = list(v["paises"])
        v["brasil"] = abre_brasil(v["paises"])
    for v in lista:
        titulo = v["titulo"].strip().lower()
        chave = (v["plataforma"], titulo, v.get("valorMin"), v.get("valorMax"))
        if chave not in principal:
            principal[chave] = v
            continue
        p = principal[chave]
        v["dup"] = True
        for pais in v["paises"]:
            if pais not in p["paises"]:
                p["paises"].append(pais)
        p["brasil"] = abre_brasil(p["paises"])


def salvar(vagas: dict[str, dict]) -> None:
    lista = sorted(vagas.values(), key=lambda v: (v.get("publicada") or "", v["id"]), reverse=True)
    marcar_duplicatas(lista)
    for v in lista:
        v["pagina"] = slug(v)
    dados = {
        "atualizado": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "plataformas": {p.nome: p.rotulo for p in PLATAFORMAS},
        "vagas": lista,
    }
    VAGAS.write_text(json.dumps(dados, ensure_ascii=False, indent=0), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="hub")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("coletar", help="busca vagas novas e retira as encerradas")
    c.add_argument("--max", type=int, default=400, help="máximo de vagas novas por plataforma")
    c.add_argument("--pausa", type=float, default=1.0, help="segundos entre requisições")
    sub.add_parser("reprocessar", help="recalcula área e países das vagas salvas, sem baixar nada")
    sub.add_parser("traduzir", help="traduz para português as vagas que ainda não têm tradução")
    sub.add_parser("paginas", help="gera a página de cada vaga, o sitemap e o robots.txt (roda na publicação)")
    n = sub.add_parser("newsletter", help="manda as vagas novas para quem confirmou a inscrição")
    n.add_argument("--simular", action="store_true", help="mostra o que seria enviado, sem mandar nada")
    n.add_argument("--teste", metavar="EMAIL", help="manda o e-mail de hoje só para este endereço")
    n.add_argument("--ligar", nargs=2, metavar=("URL_EXEC", "CHAVE"), help="liga a newsletter: grava o endereço do Apps Script no site e a chave no PC")
    a = ap.parse_args(argv)
    if a.cmd == "coletar" and (a.max < 0 or a.pausa < 0):
        ap.error("--max e --pausa não podem ser negativos")

    if a.cmd == "reprocessar":
        vagas = ler()
        for v in vagas.values():
            v["paises"] = paises_da_vaga(v.get("paisesProprios", v["paises"]))
            v["paisesProprios"] = v["paises"]
            v["brasil"] = abre_brasil(v["paises"])
            v["area"] = area_da_vaga(v["titulo"], " ".join(v["habilidades"]) + " " + v["resumo"])
        salvar(vagas)
        print(f"{len(vagas)} vagas reprocessadas")

    if a.cmd == "traduzir":
        vagas = ler()
        n = traduzir_vagas(vagas)
        salvar(vagas)
        print(f"{n} textos traduzidos")

    if a.cmd == "paginas":
        from .paginas import gerar
        print(f"{gerar()} páginas de vaga geradas")

    if a.cmd == "newsletter":
        from .newsletter import ligar, rodar
        print(ligar(*a.ligar) if a.ligar else rodar(simular=a.simular, teste=a.teste))

    if a.cmd == "coletar":
        antes = ler()
        vagas, r = coletar(antes, maximo_novas=a.max, pausa=a.pausa)
        n = traduzir_vagas(vagas)
        r["traduzidos"] = n
        salvar(vagas)
        linha = (f"{hoje()} {datetime.now():%H:%M} | total {len(vagas)} | novas {len(r['novas'])} | "
                 f"removidas {len(r['removidas'])} | traduzidos {r['traduzidos']} | erros {r['erros']}")
        print(linha)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(linha + "\n")


if __name__ == "__main__":
    main()
