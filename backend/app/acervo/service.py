"""API do acervo: ingestão no celular + leitura para a ARKHER."""
from __future__ import annotations

from pathlib import Path

from backend.app.acervo import convert


def status(root: str | None = None) -> dict:
    alvo = Path(root) if root else convert.DEFAULT_ROOT
    res = {"root": str(alvo), "existe": alvo.exists()}
    if not alvo.exists():
        return {**res, "ok": False, "xml": []}
    xml = convert.listar_xml(alvo)
    manifest = alvo / "_arkher" / "indices" / "manifest.json"
    extra = {}
    if manifest.exists():
        import json

        try:
            extra = json.loads(manifest.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            extra = {}
    return {
        "ok": True,
        **res,
        "xml": xml,
        "rbxlx": sum(1 for x in xml if x["tipo"] == "rbxlx"),
        "rbxmx": sum(1 for x in xml if x["tipo"] == "rbxmx"),
        "manifesto": {k: extra.get(k) for k in ("atualizado", "xml_rbxlx", "xml_rbxmx", "pendencias") if k in extra},
    }


def ingerir(root: str | None = None) -> dict:
    return convert.ingerir(Path(root) if root else None)


def ciclo(root: str | None = None, user_id: str = "local", limite: int = 0) -> dict:
    from backend.app.acervo import ciclo as ciclo_mod

    return ciclo_mod.rodar(Path(root) if root else None, user_id=user_id, limite=limite)


def ler(path: str) -> dict:
    p = Path(path)
    # só lê dentro de _arkher/xml para não virar file-read arbitrário
    if "_arkher" not in p.parts or p.suffix.lower() not in (".rbxlx", ".rbxmx", ".xml"):
        return {"ok": False, "code": "FORBIDDEN", "message": "Só leio XML do acervo _arkher/xml."}
    if not p.is_file():
        return {"ok": False, "code": "NOT_FOUND", "message": "Arquivo não encontrado."}
    return {"ok": True, **convert.ler_xml(p)}
