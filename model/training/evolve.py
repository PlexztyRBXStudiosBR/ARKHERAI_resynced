"""Evolução: o modelo anterior treina o próximo — sem amostra repetida.

Usa *tudo que está no disco da ARKHER* (treino pedagógico, seed, XML do
acervo, prints). Não copia pesos de IA de terceiro. SHA-256: visto → pula.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from model.training.common import CHECKPOINT_DIR, ROOT, SEED_DIR, GENERATED_DIR, log, write_state
from model.training import linhagem

SEEN = CHECKPOINT_DIR / "trained_hashes.json"
DATA = Path(os.environ.get("ARKHER_DATA_DIR", str(ROOT / "data")))
TREINOS = [
    GENERATED_DIR / "treino",
    DATA / "generated" / "treino",
]
ACERVOS = [
    Path("/storage/emulated/0/ArkherAITraining/_arkher/xml"),
    DATA / "acervo" / "xml",
]
PRINTS = [
    GENERATED_DIR / "prints",
    DATA / "generated" / "prints",
]
CORPUS = GENERATED_DIR / "evolve.txt"
XML_OK = {".rbxlx", ".rbxmx", ".xml", ".lua", ".luau", ".md", ".txt", ".py", ".json"}
IMG_OK = {".jpg", ".jpeg", ".png", ".webp"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_seen() -> dict:
    if not SEEN.exists():
        return {"hashes": {}, "atualizado": None, "modelos": []}
    try:
        return json.loads(SEEN.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"hashes": {}, "atualizado": None, "modelos": []}


def save_seen(data: dict) -> None:
    SEEN.parent.mkdir(parents=True, exist_ok=True)
    SEEN.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _iter_textos() -> list[tuple[str, str, str]]:
    """[(hash, texto, origem)] candidatos. Não filtra seen."""
    out: list[tuple[str, str, str]] = []

    def add_text(origem: str, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        out.append((sha_text(text), text[:20_000], origem))

    def head(p: Path, n: int = 20_000) -> str:
        with p.open("rb") as f:
            return f.read(n).decode("utf-8", errors="replace")

    def sha_stream(p: Path) -> tuple[str, int]:
        h = hashlib.sha256()
        n = 0
        with p.open("rb") as f:
            while True:
                b = f.read(1024 * 1024)
                if not b:
                    break
                h.update(b)
                n += len(b)
        return h.hexdigest(), n

    for treino in TREINOS:
        if not treino.exists():
            continue
        for p in sorted(treino.rglob("*")):
            if not p.is_file() or p.suffix.lower() == ".json":
                continue
            if p.suffix.lower() in IMG_OK:
                h, n = sha_stream(p)
                add_text(f"print:{p.name}", f"# print {h}\n# bytes {n}\n# arquivo {p.name}\n")
            else:
                add_text(str(p), head(p))

    if SEED_DIR.exists():
        for p in sorted(SEED_DIR.rglob("*.txt")):
            add_text(f"seed:{p.name}", head(p, 12_000))

    for acervo in ACERVOS:
        if not acervo.exists():
            continue
        for p in sorted(acervo.rglob("*")):
            if not p.is_file() or p.suffix.lower() not in XML_OK:
                continue
            add_text(f"acervo:{p.name}", head(p))

    for pasta in PRINTS:
        if not pasta.exists():
            continue
        for p in sorted(pasta.rglob("*")):
            if not p.is_file() or p.suffix.lower() not in IMG_OK:
                continue
            h, n = sha_stream(p)
            add_text(f"print:{p.name}", f"# print {h}\n# bytes {n}\n# arquivo {p.name}\n")

    return out


def amostras_novas() -> list[tuple[str, str]]:
    seen = load_seen().get("hashes", {})
    novas: list[tuple[str, str]] = []
    ja: set[str] = set()
    for h, text, _origem in _iter_textos():
        if h in seen or h in ja:
            continue
        ja.add(h)
        novas.append((h, text))
    return novas


def main() -> int:
    novas = amostras_novas()
    seen = load_seen()
    CORPUS.parent.mkdir(parents=True, exist_ok=True)
    if not novas:
        log("evolve: nenhuma amostra nova (treino repetido evitado)")
        write_state({"status": "evolve", "novas": 0, "total_hashes": len(seen.get("hashes", {}))})
        if not CORPUS.exists():
            CORPUS.write_text("", encoding="utf-8")
        plano = linhagem.plano()
        linhagem.salvar({**linhagem.carregar(), "ultimo_plano": {
            "pct": plano["pct"], "promover": plano["promover"], "gen_atual": plano["gen_atual"],
        }})
        return 0
    with CORPUS.open("a", encoding="utf-8") as f:
        for h, text in novas:
            f.write(f"\n\n# amostra {h[:16]}\n")
            f.write(text)
            f.write("\n")
            seen.setdefault("hashes", {})[h] = {"quando": now(), "origem": "evolve"}
    seen["atualizado"] = now()
    seen.setdefault("modelos", []).append({"quando": now(), "novas": len(novas), "total": len(seen["hashes"])})
    save_seen(seen)
    plano = linhagem.plano()
    linhagem.registrar(plano["gen_atual"], None, len(novas), len(seen["hashes"]))
    log(f"evolve: +{len(novas)} amostras novas; total visto={len(seen['hashes'])}; pct={plano['pct']}% gen={plano['gen_atual']} promover={plano['promover']}")
    write_state({
        "status": "evolve",
        "novas": len(novas),
        "total_hashes": len(seen["hashes"]),
        "pct": plano["pct"],
        "gen": plano["gen_atual"],
        "promover": plano["promover"],
        "params_proximo": plano["proximo"]["params_alvo"],
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
