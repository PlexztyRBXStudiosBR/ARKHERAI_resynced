"""Descoberta incremental de estruturas do produto para o corpus de treino.

Varre apenas arquivos locais do checkout, registra hashes e produz um índice
reprodutível. Nenhum segredo, node_modules, build ou arquivo binário entra no
dataset. O material só vira treino depois da validação de licença/proveniência.
"""
from __future__ import annotations
import hashlib, json, re
from datetime import datetime, timezone
from pathlib import Path
from model.training.common import ROOT, CHECKPOINT_DIR, GENERATED_DIR, write_state

IGNORE = {".git", ".venv", "node_modules", "dist", "build", "__pycache__", ".pytest_cache"}
EXTS = {".py", ".ts", ".tsx", ".js", ".luau", ".lua", ".md", ".yaml", ".yml", ".json"}
MAX_BYTES = 512_000
INDEX = CHECKPOINT_DIR / "structure_index.json"

def main() -> None:
    old = {}
    if INDEX.exists():
        try: old = json.loads(INDEX.read_text(encoding="utf-8")).get("files", {})
        except Exception: pass
    files = {}
    for p in ROOT.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in EXTS or p.stat().st_size > MAX_BYTES:
            continue
        if any(part in IGNORE for part in p.parts):
            continue
        rel = str(p.relative_to(ROOT))
        raw = p.read_bytes()
        files[rel] = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "ext": p.suffix}
    changed = sorted(k for k,v in files.items() if old.get(k,{}).get("sha256") != v["sha256"])
    removed = sorted(set(old) - set(files))
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(), "files": files, "changed": changed, "removed": removed}
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    # Cardápio seguro: o preparador pode incorporar estas fontes locais depois.
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    (GENERATED_DIR / "structure_catalog.json").write_text(json.dumps({"proveniencia":"checkout-local", "changed":changed, "removed":removed}, ensure_ascii=False, indent=2), encoding="utf-8")
    write_state({"status":"estrutura_descoberta", "arquivos":len(files), "novos_ou_alterados":len(changed), "removidos":len(removed)})
    print(f"[descoberta] {len(files)} arquivos indexados; {len(changed)} alterados; {len(removed)} removidos")
if __name__ == "__main__": main()
