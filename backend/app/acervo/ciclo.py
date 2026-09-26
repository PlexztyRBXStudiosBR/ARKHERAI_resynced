"""Ciclo do pack: 520 arquivos (alguns +100 MB) → hash → analisar → cofre → treino.

Não reprocessa SHA visto. Não mete o .rbxl inteiro no corpus.
No fim devolve a contagem de parâmetros da linhagem.
"""
from __future__ import annotations

from pathlib import Path

from backend.app.acervo import analise, cofres, convert
from backend.app.chat import dual
from model.training import linhagem
from model.training.common import GENERATED_DIR
from model.training.evolve import load_seen, save_seen, sha_text, now as evolve_now


KNOW = GENERATED_DIR / "rbxl_knowledge"


def _marcar_hashes(manifest: dict) -> int:
    seen = load_seen()
    n = 0
    treino = KNOW / "treino"
    if treino.exists():
        for p in treino.glob("*.txt"):
            text = p.read_text(encoding="utf-8", errors="replace")
            h = sha_text(text)
            if h in seen.get("hashes", {}):
                continue
            seen.setdefault("hashes", {})[h] = {"quando": evolve_now(), "origem": "ciclo_pack"}
            n += 1
    for pr in manifest.get("projects") or []:
        h = pr.get("sha256")
        if h:
            seen.setdefault("hashes", {})[h] = {"quando": evolve_now(), "origem": "ciclo_pack_arquivo"}
    seen["atualizado"] = evolve_now()
    save_seen(seen)
    return n


def rodar(root: Path | None = None, user_id: str = "local", limite: int = 0) -> dict:
    root = Path(root) if root else convert.DEFAULT_ROOT
    ingest = convert.ingerir(root)
    ja = set((load_seen().get("hashes") or {}).keys())
    fonte = root / "_arkher" / "xml"
    if not fonte.exists():
        fonte = root
    man = analise.analisar_pasta(fonte if fonte.exists() else root, KNOW, ja_visto=ja)
    if limite and len(man.get("projects") or []) > limite:
        man["projects"] = man["projects"][:limite]
    novas_treino = _marcar_hashes(man)
    # dual: só a amostra compacta
    duals = []
    treino_dir = KNOW / "treino"
    if treino_dir.exists():
        for p in sorted(treino_dir.glob("*.txt"))[: max(1, limite) if limite else 500]:
            duals.append(dual.guardar(user_id, f"pack {p.stem}", {"nome": p.name, "conteudo": p.read_text(encoding="utf-8")}))
    espelhos = []
    if treino_dir.exists():
        for p in sorted(treino_dir.glob("*.txt"))[:20]:
            espelhos.append(cofres.espelhar(p, root))
    if (KNOW / "manifest.json").exists():
        cofres.espelhar(KNOW / "manifest.json", root)
    barra = linhagem.plano()
    gigantes = [pr for pr in man.get("projects") or [] if pr.get("enorme") or (pr.get("mb") or 0) >= 100]
    return {
        "ok": True,
        "root": str(root),
        "ingest": {
            "ok": ingest.get("ok"),
            "arquivos": len(ingest.get("arquivos") or []),
            "xml_rbxlx": ingest.get("xml_rbxlx", 0),
            "xml_rbxmx": ingest.get("xml_rbxmx", 0),
            "pendencias": ingest.get("pendencias", 0),
        },
        "analise": {
            "vistos": man.get("arquivos_vistos", 0),
            "novos": man.get("novos", 0),
            "pulados_hash": man.get("pulados_hash", 0),
            "gigantes_100mb": man.get("gigantes_100mb", 0),
        },
        "gigantes": [{"nome": g.get("nome"), "mb": g.get("mb"), "sha256": (g.get("sha256") or "")[:16]} for g in gigantes[:30]],
        "treino_novas": novas_treino,
        "dual": sum(1 for d in duals if d.get("nova_para_treino")),
        "cofres": cofres.resumo(root),
        "parametros": {
            "pct": barra["pct"],
            "gen_atual": barra["gen_atual"],
            "nome": barra["atual"]["nome"],
            "params_agora": barra["params_agora_formula"],
            "params_arquitetura": barra["atual"].get("params_estimados"),
            "params_proximo": barra["proximo"]["params_alvo"],
            "proximo_nome": barra["proximo"]["nome"],
            "promover": barra["promover"],
            "formula": barra["formula"],
        },
    }
