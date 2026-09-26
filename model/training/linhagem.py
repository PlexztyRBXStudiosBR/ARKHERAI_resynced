"""Escada da ARKHER: porcentagem do produto → geração → parâmetros.

Não copia modelo de terceiro. Cada 10% do *produto* (acervo na VM, XML,
print, análise) nasce uma geração nova. O modelo anterior ensina o próximo
(cópia de pesos compatíveis + destilação). Amostra com SHA já visto não entra.

Fórmula (ancorada no mini atual = 20% → ~4 M):
    params(pct) = 4_000_000 * 2 ** ((pct - 20) / 10)

Gerações 1–4 mantêm d_model=256 (dá para copiar blocos). Da 5 em diante
alarga — aí o professor só destila logits, não cola tensor.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from model.training.common import CHECKPOINT_DIR, ROOT, log

LINHAGEM_PATH = CHECKPOINT_DIR / "linhagem.json"

# Cada degrau: 10 pontos percentuais. Alvo ≈ 4e6 * 2**((pct_min-20)/10)
ESCADA: list[dict[str, Any]] = [
    {"gen": 1, "pct_min": 0, "pct_max": 10, "nome": "ARKHER-1 nano",
     "n_layers": 2, "n_heads": 4, "d_model": 256, "d_ff": 1024,
     "context_window": 128, "vocab_size": 3072, "params_alvo": 2_000_000},
    {"gen": 2, "pct_min": 10, "pct_max": 20, "nome": "ARKHER-1 mini",
     "n_layers": 4, "n_heads": 4, "d_model": 256, "d_ff": 1024,
     "context_window": 160, "vocab_size": 3072, "params_alvo": 4_000_000},
    {"gen": 3, "pct_min": 20, "pct_max": 30, "nome": "ARKHER-1 midi",
     "n_layers": 8, "n_heads": 4, "d_model": 256, "d_ff": 1024,
     "context_window": 256, "vocab_size": 3072, "params_alvo": 8_000_000},
    {"gen": 4, "pct_min": 30, "pct_max": 40, "nome": "ARKHER-1",
     "n_layers": 16, "n_heads": 4, "d_model": 256, "d_ff": 1024,
     "context_window": 256, "vocab_size": 3072, "params_alvo": 16_000_000},
    {"gen": 5, "pct_min": 40, "pct_max": 50, "nome": "ARKHER-1 wide",
     "n_layers": 16, "n_heads": 8, "d_model": 384, "d_ff": 1536,
     "context_window": 384, "vocab_size": 3072, "params_alvo": 32_000_000},
    {"gen": 6, "pct_min": 50, "pct_max": 60, "nome": "ARKHER-2",
     "n_layers": 20, "n_heads": 8, "d_model": 512, "d_ff": 2048,
     "context_window": 512, "vocab_size": 4096, "params_alvo": 64_000_000},
    {"gen": 7, "pct_min": 60, "pct_max": 70, "nome": "ARKHER-2+",
     "n_layers": 24, "n_heads": 12, "d_model": 768, "d_ff": 3072,
     "context_window": 512, "vocab_size": 8192, "params_alvo": 128_000_000},
    {"gen": 8, "pct_min": 70, "pct_max": 80, "nome": "ARKHER-3",
     "n_layers": 28, "n_heads": 16, "d_model": 1024, "d_ff": 4096,
     "context_window": 768, "vocab_size": 16384, "params_alvo": 256_000_000},
    {"gen": 9, "pct_min": 80, "pct_max": 90, "nome": "ARKHER-3+",
     "n_layers": 32, "n_heads": 16, "d_model": 1280, "d_ff": 5120,
     "context_window": 1024, "vocab_size": 32768, "params_alvo": 512_000_000},
    {"gen": 10, "pct_min": 90, "pct_max": 100, "nome": "ARKHER-4",
     "n_layers": 36, "n_heads": 20, "d_model": 1536, "d_ff": 6144,
     "context_window": 1024, "vocab_size": 32768, "params_alvo": 1_000_000_000},
]


def estimar_parametros(
    vocab_size: int,
    context_window: int,
    n_layers: int,
    d_model: int,
    d_ff: int,
    tie_embeddings: bool = True,
) -> int:
    """Conta fechada igual ao Arkher1 (Linear sem bias, LN com bias, head amarrado)."""
    emb = vocab_size * d_model
    pos = context_window * d_model
    layer = 4 * d_model * d_model + 2 * d_model * d_ff + 4 * d_model
    ln_f = 2 * d_model
    head = 0 if tie_embeddings else vocab_size * d_model
    return emb + pos + n_layers * layer + ln_f + head


def params_pela_pct(pct: float) -> int:
    """4 M no degrau de 20%; dobra a cada +10 pontos."""
    pct = max(0.0, min(100.0, float(pct)))
    return int(round(4_000_000 * (2 ** ((pct - 20.0) / 10.0))))


def rung_por_pct(pct: float) -> dict[str, Any]:
    pct = max(0.0, min(100.0, float(pct)))
    for r in ESCADA:
        if r["pct_min"] <= pct < r["pct_max"] or (r["gen"] == 10 and pct >= 90):
            return dict(r)
    return dict(ESCADA[1])


def rung_por_gen(gen: int) -> dict[str, Any]:
    for r in ESCADA:
        if r["gen"] == int(gen):
            return dict(r)
    raise ValueError(f"geração inexistente: {gen}")


def proximo(rung: dict[str, Any]) -> dict[str, Any] | None:
    g = int(rung["gen"])
    if g >= 10:
        return None
    return rung_por_gen(g + 1)


def enriquecer(rung: dict[str, Any]) -> dict[str, Any]:
    r = dict(rung)
    r["params_estimados"] = estimar_parametros(
        r["vocab_size"], r["context_window"], r["n_layers"], r["d_model"], r["d_ff"]
    )
    r["params_formula"] = params_pela_pct((r["pct_min"] + r["pct_max"]) / 2)
    return r


def _existe(*parts: str) -> bool:
    return (ROOT.joinpath(*parts)).exists()


def _conta(glob: str, base: Path) -> int:
    if not base.exists():
        return 0
    return sum(1 for p in base.glob(glob) if p.is_file())


def produto_barra() -> dict[str, Any]:
    """Porcentagem honesta do *ciclo do pack*, não de GPU.

    Pesos somam 100. Código no repo não conta como pack ingerido.
    """
    xml_dir = Path("/storage/emulated/0/ArkherAITraining/_arkher/xml")
    knowledge = ROOT / "model" / "datasets" / "generated" / "rbxl_knowledge" / "manifest.json"
    prints = ROOT / "model" / "datasets" / "generated" / "prints"
    seen = CHECKPOINT_DIR / "trained_hashes.json"
    hashes = 0
    if seen.exists():
        try:
            hashes = len(json.loads(seen.read_text(encoding="utf-8")).get("hashes") or {})
        except json.JSONDecodeError:
            hashes = 0
    projetos = 0
    if knowledge.exists():
        try:
            projetos = len(json.loads(knowledge.read_text(encoding="utf-8")).get("projects") or [])
        except json.JSONDecodeError:
            projetos = 0
    xml_n = _conta("**/*", xml_dir) if xml_dir.exists() else 0
    print_n = _conta("*.jpg", prints) + _conta("*.jpeg", prints) + _conta("*.png", prints)
    agent = (ROOT / "workers" / "workspace" / "agent.py").read_text(encoding="utf-8") if _existe("workers", "workspace", "agent.py") else ""
    pack = max(xml_n, projetos)
    # 520 arquivos = degrau cheio desses pesos. 1 place não pula 4 gerações.
    def _pts(peso: int, n: int, alvo: int = 520) -> int:
        if n <= 0:
            return 0
        return max(1, round(peso * min(1.0, n / alvo)))

    itens = [
        {"id": "casco", "peso": 4, "ok": _existe("frontend", "src", "app", "app.ts"), "detalhe": "site/abas", "pontos": 4},
        {"id": "checkpoint", "peso": 4, "ok": (CHECKPOINT_DIR / "latest.pt").exists(), "detalhe": "ARKHER-1 mini no disco", "pontos": 4 if (CHECKPOINT_DIR / "latest.pt").exists() else 0},
        {"id": "geradores", "peso": 4, "ok": _existe("backend", "app", "studio", "kits.py"), "detalhe": "studio próprio", "pontos": 4},
        {"id": "vm_protocolo", "peso": 4, "ok": "def screenshot" in agent and "def install_app" in agent, "detalhe": "print/clique/instala no agente", "pontos": 4 if ("def screenshot" in agent and "def install_app" in agent) else 0},
        {"id": "hash_evolve", "peso": 4, "ok": True, "detalhe": f"{hashes} hashes vistos", "pontos": 4},
        {"id": "acervo_xml", "peso": 18, "ok": pack > 0, "detalhe": f"{xml_n} XML / {projetos} extraídos (alvo 520)", "pontos": _pts(18, pack)},
        {"id": "analise_pack", "peso": 16, "ok": projetos > 0, "detalhe": f"{projetos} jogos extraídos", "pontos": _pts(16, projetos)},
        {"id": "print_treino", "peso": 14, "ok": print_n > 0, "detalhe": f"{print_n} prints no corpus", "pontos": _pts(14, print_n, 80)},
        {"id": "cofres", "peso": 10, "ok": False, "detalhe": "vários storages ainda não ligados", "pontos": 0},
        {"id": "promovida", "peso": 10, "ok": False, "detalhe": "geração > 2 só depois do pack", "pontos": 0},
    ]
    # promovida: lê linhagem se existir
    snap = carregar()
    if snap.get("gen_atual", 2) > 2:
        for it in itens:
            if it["id"] == "promovida":
                it["ok"] = True
                it["pontos"] = it["peso"]
                it["detalhe"] = f"gen {snap['gen_atual']}"
    pct = min(100, sum(int(it.get("pontos") or 0) for it in itens))
    return {"pct": pct, "itens": itens, "xml": xml_n, "projetos": projetos, "prints": print_n, "hashes": hashes}


def gen_do_checkpoint(path: Path | None = None) -> int:
    p = path or (CHECKPOINT_DIR / "latest.pt")
    if not p.exists():
        return 2
    try:
        import torch  # type: ignore

        payload = torch.load(p, map_location="cpu", weights_only=False)
        cfg = payload.get("config") or {}
        layers = int(cfg.get("n_layers") or 4)
        d = int(cfg.get("d_model") or 256)
        for r in ESCADA:
            if r["n_layers"] == layers and r["d_model"] == d:
                return int(r["gen"])
        meta = payload.get("meta") or {}
        if meta.get("gen"):
            return int(meta["gen"])
    except Exception:
        pass
    snap = carregar()
    return int(snap.get("gen_atual") or 2)


def deve_promover(pct: float, gen_atual: int) -> bool:
    alvo = int(rung_por_pct(pct)["gen"])
    return alvo > int(gen_atual)


def copiar_state_compativel(src: dict, dst: dict) -> int:
    """Copia tensores de mesmo nome e shape. Blocos extra do aluno ficam virgens."""
    n = 0
    for k, v in list(dst.items()):
        if k not in src:
            continue
        a, b = src[k], v
        sa = getattr(a, "shape", None)
        sb = getattr(b, "shape", None)
        if sa is not None and sa == sb:
            dst[k] = a.detach().clone() if hasattr(a, "detach") else a
            n += 1
        elif sa is None and type(a) is type(b):
            dst[k] = a
            n += 1
    return n


def carregar() -> dict[str, Any]:
    if not LINHAGEM_PATH.exists():
        return {"gen_atual": 2, "modelos": []}
    try:
        return json.loads(LINHAGEM_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"gen_atual": 2, "modelos": []}


def salvar(data: dict[str, Any]) -> None:
    LINHAGEM_PATH.parent.mkdir(parents=True, exist_ok=True)
    LINHAGEM_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def plano(pct: float | None = None, gen_atual: int | None = None) -> dict[str, Any]:
    barra = produto_barra()
    pct_informada = pct is not None
    pct = barra["pct"] if pct is None else float(pct)
    gen_atual = gen_do_checkpoint() if gen_atual is None else int(gen_atual)
    atual = enriquecer(rung_por_gen(gen_atual))
    alvo = enriquecer(rung_por_pct(pct))
    nxt = enriquecer(proximo(atual) or atual)
    promo = deve_promover(pct, gen_atual)
    if not pct_informada and not (barra["projetos"] > 0 or barra["xml"] > 0):
        promo = False
    return {
        "ok": True,
        "pct": pct,
        "barra": barra,
        "gen_atual": gen_atual,
        "atual": atual,
        "alvo_pela_pct": alvo,
        "proximo": nxt,
        "promover": promo,
        "regra": "cada 10% do produto = geração nova; professor = modelo anterior; hash SHA-256 não repete amostra",
        "formula": "params = 4e6 * 2^((pct-20)/10)",
        "params_agora_formula": params_pela_pct(pct),
        "params_proximo_formula": params_pela_pct(min(100, (nxt["pct_min"] + nxt["pct_max"]) / 2)),
    }


def registrar(gen: int, professor: str | None, novas: int, total_hashes: int) -> dict[str, Any]:
    data = carregar()
    data["gen_atual"] = int(gen)
    data.setdefault("modelos", []).append({
        "quando": datetime.now(timezone.utc).isoformat(),
        "gen": int(gen),
        "professor": professor,
        "novas": novas,
        "total_hashes": total_hashes,
        "nome": rung_por_gen(gen)["nome"],
    })
    data["atualizado"] = datetime.now(timezone.utc).isoformat()
    salvar(data)
    log(f"linhagem: gen {gen} ({rung_por_gen(gen)['nome']}); professor={professor or '—'}")
    return data


def main() -> int:
    p = plano()
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    (CHECKPOINT_DIR / "linhagem_plano.json").write_text(
        json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log(
        f"pct={p['pct']}% gen_atual={p['gen_atual']} "
        f"params_formula={p['params_agora_formula']:,} promover={p['promover']} "
        f"próximo={p['proximo']['nome']} ~{p['proximo']['params_alvo']:,}"
    )
    print(json.dumps({k: p[k] for k in ("pct", "gen_atual", "promover", "params_agora_formula", "regra")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
