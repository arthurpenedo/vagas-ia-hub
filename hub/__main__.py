"""python -m hub coletar  → atualiza site/vagas.json e escreve o log da rodada."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from .classificar import abre_brasil, area_da_vaga, paises_da_vaga
from .coleta import PLATAFORMAS, coletar, hoje

RAIZ = Path(__file__).resolve().parents[1]
VAGAS = RAIZ / "site" / "vagas.json"
LOG = RAIZ / "coletas.log"


def ler() -> dict[str, dict]:
    if not VAGAS.exists():
        return {}
    return {v["id"]: v for v in json.loads(VAGAS.read_text(encoding="utf-8"))["vagas"]}


def salvar(vagas: dict[str, dict]) -> None:
    lista = sorted(vagas.values(), key=lambda v: (v.get("publicada") or "", v["id"]), reverse=True)
    dados = {
        "atualizado": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "plataformas": {p.nome: p.rotulo for p in PLATAFORMAS},
        "vagas": lista,
    }
    VAGAS.write_text(json.dumps(dados, ensure_ascii=False, indent=0), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(prog="hub")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("coletar", help="busca vagas novas e retira as encerradas")
    c.add_argument("--max", type=int, default=400, help="máximo de vagas novas por plataforma")
    c.add_argument("--pausa", type=float, default=1.0, help="segundos entre requisições")
    sub.add_parser("reprocessar", help="recalcula área e países das vagas salvas, sem baixar nada")
    a = ap.parse_args()

    if a.cmd == "reprocessar":
        vagas = ler()
        for v in vagas.values():
            v["paises"] = paises_da_vaga(v["paises"])
            v["brasil"] = abre_brasil(v["paises"])
            v["area"] = area_da_vaga(v["titulo"], " ".join(v["habilidades"]) + " " + v["resumo"])
        salvar(vagas)
        print(f"{len(vagas)} vagas reprocessadas")

    if a.cmd == "coletar":
        antes = ler()
        vagas, r = coletar(antes, maximo_novas=a.max, pausa=a.pausa)
        salvar(vagas)
        linha = (f"{hoje()} {datetime.now():%H:%M} | total {len(vagas)} | novas {len(r['novas'])} | "
                 f"removidas {len(r['removidas'])} | erros {r['erros']}")
        print(linha)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(linha + "\n")


if __name__ == "__main__":
    main()
