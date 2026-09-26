"""Duas versões de cada artefato: a do usuário e a de treino.

A versão do usuário segue o pedido e só acrescenta o necessário para
funcionar (spawn, luz, colisão, script mínimo).
A versão de treino é arquivada para o *próximo* modelo — com anotações
pedagógicas — e nunca reentra no treino se o hash já foi visto.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from backend.app import config

TREINO_DIR = config.DATA_DIR / "generated" / "treino"
USER_DIR = config.DATA_DIR / "generated" / "usuario"
SEEN_PATH = config.DATA_DIR / "trained_hashes.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_seen() -> dict:
    if not SEEN_PATH.exists():
        return {"hashes": {}, "atualizado": None}
    try:
        return json.loads(SEEN_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"hashes": {}, "atualizado": None}


def ja_treinada(conteudo: str) -> bool:
    return sha(conteudo) in _load_seen().get("hashes", {})


def marcar_treinada(conteudo: str, origem: str = "dual") -> None:
    data = _load_seen()
    data.setdefault("hashes", {})[sha(conteudo)] = {"quando": _now(), "origem": origem}
    data["atualizado"] = _now()
    SEEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    SEEN_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def versao_treino(pedido: str, conteudo: str, nome: str) -> str:
    """Anota o artefato para o próximo ciclo — sem alterar a versão do usuário."""
    cabeca = (
        f"-- ARKHER TREINO v1\n"
        f"-- pedido: {pedido[:200]}\n"
        f"-- arquivo: {nome}\n"
        f"-- gerado: {_now()}\n"
        f"-- regra: amostra nova (hash {sha(conteudo)[:16]}); não re-treinar se visto\n"
        f"-- pedagogia: estrutura, nomenclatura, replicação, colisão, spawn, iluminação\n"
    )
    if nome.endswith((".rbxlx", ".rbxmx", ".xml")):
        nota = (
            f"<!--\n{cabeca}-->\n"
        )
        if conteudo.lstrip().startswith("<?xml"):
            linhas = conteudo.split("\n", 1)
            return linhas[0] + "\n" + nota + (linhas[1] if len(linhas) > 1 else "")
        return nota + conteudo
    if nome.endswith(".lua") or "luau" in nome:
        return cabeca.replace("-- ", "-- ") + "\n" + conteudo
    if nome.endswith(".py"):
        return "\n".join("# " + ln[3:] if ln.startswith("-- ") else "# " + ln for ln in cabeca.splitlines()) + "\n" + conteudo
    return cabeca + "\n" + conteudo


def guardar(user_id: str, pedido: str, arquivo: dict | None) -> dict:
    """Persiste as duas versões. Retorna metadados (sem duplicar treino)."""
    if not arquivo or not arquivo.get("conteudo"):
        return {"ok": False, "motivo": "sem_conteudo"}
    nome = str(arquivo.get("nome") or "artefato.txt")
    conteudo = str(arquivo["conteudo"])
    h = sha(conteudo)
    USER_DIR.mkdir(parents=True, exist_ok=True)
    TREINO_DIR.mkdir(parents=True, exist_ok=True)
    seguro = re.sub(r"[^\w.\-]+", "_", nome)[:80]
    user_path = USER_DIR / f"{h[:12]}_{seguro}"
    user_path.write_text(conteudo, encoding="utf-8")
    treino_nova = not ja_treinada(conteudo)
    treino_path = TREINO_DIR / f"{h[:12]}_{seguro}"
    if treino_nova:
        treino_path.write_text(versao_treino(pedido, conteudo, nome), encoding="utf-8")
        # ainda não marca como treinada — só quando o ciclo de treino consumir
        meta = {
            "hash": h,
            "pedido": pedido[:400],
            "user_id": user_id,
            "quando": _now(),
            "arquivo": nome,
            "nova_para_treino": True,
        }
        (TREINO_DIR / f"{h[:12]}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "ok": True,
        "hash": h,
        "usuario": str(user_path),
        "treino": str(treino_path) if treino_nova else None,
        "nova_para_treino": treino_nova,
    }
