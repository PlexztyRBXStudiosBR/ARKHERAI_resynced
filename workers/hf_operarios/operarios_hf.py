"""Operários de aprendizagem — modelos ABERTOS do Hugging Face a serviço do treino.

Conceito: a ARKHER continua 100% própria (nenhum peso externo no modelo dela).
Mas modelos abertos do HF Hub, rodando NO SEU hardware (PC/Kaggle/Colab), podem
trabalhar como OPERÁRIOS do treino da ARKHER:

  1. gerar   — produz pares instrução→resposta sobre o nicho (game dev, Roblox,
               Blender, engines), sempre com proveniência registrada;
  2. avaliar — lê respostas geradas pela ARKHER e devolve notas/erros, criando
               dados de correção (o "conselho" que avalia sem humano);
  3. filtrar — marca dados irrelevantes/duplicados para descarte ou referência.

Isto NÃO roda no runtime do produto: é script de treino offline, executado por
você, nos seus recursos. Saída: JSONL em model/datasets/externo/ com licença e
origem declaradas — o validate_dataset.py continua sendo o porteiro.

Uso (no seu ambiente, com transformers instalado):
  python workers/hf_operarios/operarios_hf.py gerar \
      --modelo "Qwen/Qwen2.5-Coder-1.5B-Instruct" --pares 200
  python workers/hf_operarios/operarios_hf.py avaliar \
      --modelo "Qwen/Qwen2.5-Coder-1.5B-Instruct" --respostas arkher_respostas.jsonl
  python workers/hf_operarios/operarios_hf.py filtrar --jsonl model/datasets/externo/gerado.jsonl

Sem GPU? Rode com --amostra pequena; o importante é o ciclo, não a velocidade.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SAIDA = ROOT / "model" / "datasets" / "externo"

# Nichos onde a ARKHER quer ser especialista. Cada operário sorteia temas daqui.
NICHOS = [
    "criar um sistema de salvamento (DataStore) no Roblox Studio",
    "fazer um personagem andar e pular na Godot 4",
    "modelar um cenário low-poly no Blender por script",
    "escrever um leaderstats com pontos no Roblox",
    "explicar o que é um game loop e delta time",
    "criar um terreno heightmap e exportar como OBJ",
    "fazer uma animação de corrida simples no Blender",
    "otimizar draw calls num jogo mobile",
    "explicar ECS (Entity Component System) com exemplo",
    "criar um sistema de checkpoint/obby no Roblox",
]

PROMPT_GERAR = (
    "Você é um operário de treino da ARKHER AI (assistente de game dev). "
    "Escreva UM par de treino em JSON com as chaves 'instrucao' e 'resposta' "
    "sobre: {tema}. Resposta correta, prática, em português, 80-160 palavras. "
    "Responda APENAS o JSON."
)

PROMPT_AVALIAR = (
    "Avalie esta resposta de um assistente de game dev quanto a correção e "
    "utilidade (0 a 10) e aponte erros. Responda JSON: "
    "{{\"nota\": N, \"erros\": [\"...\"], \"melhoria\": \"...\"}}.\n\n"
    "Pergunta: {pergunta}\nResposta: {resposta}"
)


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _carregar_modelo(nome: str):
    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as e:  # honesto: dependência do operário, não do produto
        raise SystemExit(
            "Operário requer 'transformers' no ambiente ONDE VOCÊ RODA "
            "(pip install transformers). O produto ARKHER em si não usa."
        ) from e
    tok = AutoTokenizer.from_pretrained(nome)
    mdl = AutoModelForCausalLM.from_pretrained(nome)
    return tok, mdl


def _gerar_texto(tok, mdl, prompt: str) -> str:
    import torch

    ids = tok(prompt, return_tensors="pt")
    with torch.no_grad():
        out = mdl.generate(**ids, max_new_tokens=400, do_sample=True, temperature=0.7)
    return tok.decode(out[0][ids["input_ids"].shape[1]:], skip_special_tokens=True).strip()


def _json_seguro(texto: str) -> dict | None:
    m = re.search(r"\{.*\}", texto, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def comando_gerar(args: argparse.Namespace) -> None:
    import random

    SAIDA.mkdir(parents=True, exist_ok=True)
    tok, mdl = _carregar_modelo(args.modelo)
    rng = random.Random(args.seed)
    destino = SAIDA / f"operario_gerado_{datetime.now():%Y%m%d_%H%M%S}.jsonl"
    aceitos = 0
    with destino.open("w", encoding="utf-8") as f:
        for _ in range(args.pares):
            tema = rng.choice(NICHOS)
            bruto = _gerar_texto(tok, mdl, PROMPT_GERAR.format(tema=tema))
            par = _json_seguro(bruto)
            if not par or "instrucao" not in par or "resposta" not in par:
                continue
            registro = {
                "instrucao": str(par["instrucao"])[:500],
                "resposta": str(par["resposta"])[:1200],
                "proveniencia": {
                    "origem": "operario_hf",
                    "modelo_operario": args.modelo,
                    "tema": tema,
                    "licenca": "sintetico-gerado-por-modelo-aberto",
                    "gerado_em": _agora(),
                    "hash": hashlib.sha256(bruto.encode()).hexdigest()[:16],
                },
            }
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")
            aceitos += 1
    print(f"[operário] {aceitos} pares em {destino}")
    print("[operário] revise e só então inclua no prepare_dataset (porteiro: validate_dataset).")


def comando_avaliar(args: argparse.Namespace) -> None:
    fonte = Path(args.respostas)
    if not fonte.exists():
        raise SystemExit(f"arquivo não encontrado: {fonte}")
    tok, mdl = _carregar_modelo(args.modelo)
    SAIDA.mkdir(parents=True, exist_ok=True)
    destino = SAIDA / f"operario_avaliacao_{datetime.now():%Y%m%d_%H%M%S}.jsonl"
    n = 0
    with destino.open("w", encoding="utf-8") as f:
        for linha in fonte.read_text(encoding="utf-8").splitlines():
            if not linha.strip():
                continue
            item = json.loads(linha)
            bruto = _gerar_texto(
                tok, mdl,
                PROMPT_AVALIAR.format(pergunta=item.get("pergunta", ""), resposta=item.get("resposta", "")),
            )
            nota = _json_seguro(bruto) or {"nota": None, "erros": [], "melhoria": bruto[:300]}
            f.write(json.dumps({**item, "avaliacao_operario": nota, "modelo_operario": args.modelo}, ensure_ascii=False) + "\n")
            n += 1
    print(f"[operário] {n} respostas avaliadas em {destino}")


def comando_filtrar(args: argparse.Namespace) -> None:
    """Marca duplicados/curtos demais para descarte (referência fica no arquivo)."""
    fonte = Path(args.jsonl)
    if not fonte.exists():
        raise SystemExit(f"arquivo não encontrado: {fonte}")
    vistos: set[str] = set()
    manter, descartar = 0, 0
    tmp = fonte.with_suffix(".tmp.jsonl")
    with tmp.open("w", encoding="utf-8") as f:
        for linha in fonte.read_text(encoding="utf-8").splitlines():
            if not linha.strip():
                continue
            item = json.loads(linha)
            texto = item.get("instrucao", "") + item.get("resposta", "")
            h = hashlib.sha256(texto.encode()).hexdigest()[:16]
            if h in vistos or len(texto) < 40:
                item["_descartado"] = True
                descartar += 1
            else:
                vistos.add(h)
                manter += 1
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    tmp.replace(fonte)
    print(f"[operário] mantidos={manter} descartados(marcados)={descartar}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Operários de aprendizagem (HF abertos, offline, seus recursos)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gerar", help="gera pares instrução→resposta com proveniência")
    g.add_argument("--modelo", required=True)
    g.add_argument("--pares", type=int, default=50)
    g.add_argument("--seed", type=int, default=42)
    a = sub.add_parser("avaliar", help="avalia respostas da ARKHER (conselho sem humano)")
    a.add_argument("--modelo", required=True)
    a.add_argument("--respostas", required=True)
    f = sub.add_parser("filtrar", help="marca duplicados/curtos para descarte")
    f.add_argument("--jsonl", required=True)
    args = ap.parse_args()
    {"gerar": comando_gerar, "avaliar": comando_avaliar, "filtrar": comando_filtrar}[args.cmd](args)


if __name__ == "__main__":
    main()
