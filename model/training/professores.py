"""Professores no disco: a ARKHER pode *aprender* com eles. Nunca no chat.

- Checkpoint ARKHER (.pt com config da casa) → destilação (--teacher).
- Outro peso no disco → não carrega no runtime; aponta para operário HF
  no *seu* hardware (já é a regra de treino).
"""
from __future__ import annotations

import os
from pathlib import Path

from model.training.common import CHECKPOINT_DIR, ROOT, log

EXTRA = Path(os.environ.get("ARKHER_PROFESSORES", str(ROOT / "data" / "professores")))


def pastas() -> list[Path]:
    return [CHECKPOINT_DIR, EXTRA]


def inspecionar(p: Path) -> dict:
    rec = {
        "path": str(p),
        "nome": p.name,
        "bytes": p.stat().st_size if p.exists() else 0,
        "uso": "treino_somente",
        "chat": False,
    }
    if p.suffix.lower() not in {".pt", ".pth", ".bin", ".ckpt"}:
        rec.update({"ok": False, "motivo": "extensão fora da lista de professor"})
        return rec
    try:
        import torch  # type: ignore

        payload = torch.load(p, map_location="cpu", weights_only=False)
    except Exception as e:  # noqa: BLE001
        rec.update({"ok": False, "motivo": f"não abriu como professor ARKHER: {type(e).__name__}"})
        return rec
    cfg = payload.get("config") if isinstance(payload, dict) else None
    if not isinstance(cfg, dict) or "n_layers" not in cfg:
        rec.update({
            "ok": False,
            "motivo": "peso de terceiro — não entra no chat; use como operário de treino no seu hardware",
        })
        return rec
    rec.update({
        "ok": True,
        "compativel": True,
        "n_layers": cfg.get("n_layers"),
        "d_model": cfg.get("d_model"),
        "gen": (payload.get("meta") or {}).get("gen"),
        "motivo": "professor ARKHER: destila o próximo; fora do chat",
    })
    return rec


def listar() -> dict:
    itens = []
    for pasta in pastas():
        if not pasta.exists():
            continue
        for p in sorted(pasta.glob("*")):
            if p.is_file() and p.suffix.lower() in {".pt", ".pth", ".bin", ".ckpt"}:
                itens.append(inspecionar(p))
    ok = [i for i in itens if i.get("ok")]
    return {
        "ok": True,
        "regra": "modelo no disco só ensina a ARKHER; o chat é o cérebro próprio",
        "professores": itens,
        "aptos_destilar": len(ok),
    }


def professor_padrao() -> str | None:
    latest = CHECKPOINT_DIR / "latest.pt"
    if latest.exists():
        return str(latest)
    return None


def main() -> int:
    d = listar()
    log(f"professores no disco: {d['aptos_destilar']} aptos / {len(d['professores'])} arquivos")
    for i in d["professores"]:
        log(f"  {i['nome']}: chat=NÃO ok={i.get('ok')} {i.get('motivo', '')[:80]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
