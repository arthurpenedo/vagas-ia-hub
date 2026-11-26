"""Tradução inglês → português no próprio PC, sem API paga.

Usa o modelo OPUS-MT (CC-BY 4.0) empacotado pelo Argos Translate, rodando no ctranslate2.
Cada texto é traduzido uma vez e guardado em `site/traducoes.json`, então a rotina diária só
traduz o que é novo. Sem o modelo instalado, devolve o texto original (o site continua funcionando).
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
MODELO = RAIZ / "modelos" / "translate-en_pt-1_9"
CACHE = RAIZ / "dados" / "traducoes.json"

# Termos que a tradução automática estraga ou que o mercado usa em inglês mesmo.
MANTER = ["Mercor", "micro1", "LLM", "LLMs", "RLHF", "Python", "JavaScript", "TypeScript", "SQL", "Excel",
          "Toast POS", "SaaS", "CAD", "CAM", "CNC", "SOC", "UX", "UI", "QA", "API", "APIs", "SME", "PhD", "MD", "DO",
          "MBBS", "JD", "CPA", "CFA", "STEM", "B2B", "B2C", "CRM", "ERP", "SAP", "iOS", "Android", "GitHub", "Prompt", "Prompts",
          "Unreal Engine", "Unity", "Windows", "macOS", "Linux", "Origin", "Vivado", "Figma", "Blender", "Photoshop",
          "Salesforce", "Shopify", "Venmo", "TripIt", "Cozi", "Lowe’s", "Ace Hardware", "Rocket Mortgage", "Concur",
          "Greenhouse", "Autodesk Fusion", "Core"]
# Correções pós-tradução (português europeu → brasileiro, termos do setor).
CORRIGIR = [
    (r"\bIA\b", "IA"), (r"\bIa\b", "IA"),
    (r"\bequipa\b", "equipe"), (r"\bequipas\b", "equipes"), (r"\bregisto\b", "registro"),
    (r"\bcontacto\b", "contato"), (r"\bfacto\b", "fato"), (r"\bactual\b", "atual"), (r"\bactualmente\b", "atualmente"),
    (r"\butilizador(es)?\b", r"usuário\1"), (r"\becrã\b", "tela"), (r"\bficheiro(s)?\b", r"arquivo\1"),
    (r"\bfreelancer\b", "freelancer"), (r"\bcontratado independente\b", "prestador de serviço"),
    (r"\bEntrevista de Pesquisa Paga\b", "Entrevista de pesquisa remunerada"),
    (r"\bS[ée]nior\b", "Sênior"), (r"\bInvestiga[çc][ãa]o\b", "Pesquisa"), (r"\binvestiga[çc][ãa]o\b", "pesquisa"),
    (r"\bNeste papel\b", "Nesta função"), (r"\bneste papel\b", "nesta função"), (r"\bPapel de\b", "Função de"),
    (r"\best[áa] envolvendo\b", "está contratando"), (r"\bAI Agent Tester\b", "Testador de agentes de IA"),
    (r"\bAuditor Rubric de\b", "Auditor de rubricas de"), (r"\bcandidatar-se\b", "se candidatar"),
    (r"\bAvaliador de Resposta & Resposta\b", "Avaliador de prompts e respostas"),
    (r"\best[áa] a envolver\b", "está contratando"), (r"\bprojecto(s)?\b", r"projeto\1"), (r"\bdirecto\b", "direto"),
    (r"\bPeritos\b", "Especialistas"), (r"\bperitos\b", "especialistas"), (r"\bPerito\b", "Especialista"),
    (r"\b[Aa]prendizagem de [Mm]áquina\b", "aprendizado de máquina"), (r"\bCodificador\b", "Programador"),
    (r"\bcodificador\b", "programador"), (r"\bgeneralismo\b", "conhecimentos gerais"),
    (r"^Agente Engenheiro\b", "Engenheiro de Agentes de IA"), (r"\bAgente Engenheiro\b", "Engenheiro de agentes de IA"),
    # "está a trabalhar" (Portugal) → "está trabalhando" (Brasil)
    (r"\b(est[áa]|est[ãa]o|estamos|estou) a (\w+?)ar\b", r"\1 \2ando"),
    (r"\b(est[áa]|est[ãa]o|estamos|estou) a (\w+?)er\b", r"\1 \2endo"),
    (r"\b(est[áa]|est[ãa]o|estamos|estou) a (\w+?)ir\b", r"\1 \2indo"),
]


def corrigir(t: str) -> str:
    for a, b in CORRIGIR:
        t = re.sub(a, b, t)
    return t.strip()


def _chave(texto: str) -> str:
    return hashlib.sha1(texto.encode("utf-8")).hexdigest()[:16]


class Tradutor:
    def __init__(self):
        self.cache: dict[str, str] = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
        self._motor = None
        self.novas = 0

    @property
    def disponivel(self) -> bool:
        return (MODELO / "model" / "model.bin").exists()

    def _carregar(self):
        if self._motor is None:
            import ctranslate2
            import sentencepiece as spm
            self._sp = spm.SentencePieceProcessor(model_file=str(MODELO / "sentencepiece.model"))
            self._motor = ctranslate2.Translator(str(MODELO / "model"), device="cpu", inter_threads=2)
        return self._motor

    @staticmethod
    def _frases(texto: str) -> list[str]:
        return [f for f in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"“(])", texto.strip()) if f]

    def _proteger(self, frase: str) -> tuple[str, dict[str, str]]:
        guardados = {}
        for i, termo in enumerate(sorted(MANTER, key=len, reverse=True)):
            padrao = r"(?<![\w-])" + re.escape(termo) + r"(?![\w-])"
            if re.search(padrao, frase):
                marca = f"ZQ{i}Q"
                guardados[marca] = termo
                frase = re.sub(padrao, marca, frase)
        # siglas e marcas em caixa alta (CARFAX, NCLEX, HIPAA) ficam como estão
        siglas = sorted({s for s in re.findall(r"\b[A-Z]{3,}\b", frase) if not re.fullmatch(r"Z[QX]\d+[QX]", s)})
        for j, sigla in enumerate(siglas):
            marca = f"ZX{j}X"
            guardados[marca] = sigla
            frase = re.sub(r"\b" + re.escape(sigla) + r"\b", marca, frase)
        return frase, guardados

    def _traduzir_lote(self, frases: list[str]) -> list[str]:
        motor = self._carregar()
        protegidas = [self._proteger(f) for f in frases]
        tokens = [self._sp.encode(f, out_type=str) for f, _ in protegidas]
        saida = motor.translate_batch(tokens, beam_size=2, max_decoding_length=256, repetition_penalty=1.15, no_repeat_ngram_size=4)
        out = []
        for r, (_, guardados) in zip(saida, protegidas):
            t = "".join(r.hypotheses[0]).replace("▁", " ").strip()
            for marca, termo in guardados.items():
                t = re.sub(re.escape(marca), termo, t, flags=re.I)
            out.append(corrigir(t))
        # tradução que "travou" repetindo palavras: melhor deixar o original
        return [f if re.search(r"\b(\w+)(?:\W+\1\b){2,}", o, re.I) else o for o, f in zip(out, frases)]

    def traduzir(self, texto: str) -> str:
        texto = (texto or "").strip()
        if not texto:
            return ""
        k = _chave(texto)
        if k in self.cache:
            # reaplica as correções: uma correção nova vale também para o que já foi traduzido
            self.cache[k] = corrigir(self.cache[k])
            return self.cache[k]
        if not self.disponivel:
            return texto
        frases = self._frases(texto)
        traduzido = " ".join(self._traduzir_lote(frases))
        self.cache[k] = traduzido
        self.novas += 1
        return traduzido

    def salvar(self) -> None:
        CACHE.parent.mkdir(exist_ok=True)
        CACHE.write_text(json.dumps(self.cache, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")


def traduzir_vagas(vagas: dict[str, dict], log=print) -> int:
    """Preenche tituloPt e resumoPt. Devolve quantos textos novos foram traduzidos."""
    t = Tradutor()
    if not t.disponivel:
        log("tradução: modelo não instalado, vagas ficam em inglês")
        return 0
    for v in vagas.values():
        v["tituloPt"] = t.traduzir(v["titulo"])
        v["resumoPt"] = t.traduzir(v.get("resumo", ""))
    t.salvar()
    return t.novas
