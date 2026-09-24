"""Banco de protótipos para o ciclo contínuo.

Cria variações de tarefas de game-dev a partir das estruturas detectadas.
São tarefas de avaliação/produção, não são tratadas como verdade automaticamente:
saídas precisam passar por testes e revisão antes de virar dado de treino.
"""
from __future__ import annotations
import json, hashlib
from datetime import datetime, timezone
from pathlib import Path
from model.training.common import CHECKPOINT_DIR, GENERATED_DIR

def main() -> None:
    catalog = GENERATED_DIR / "structure_catalog.json"
    changed = json.loads(catalog.read_text(encoding="utf-8")).get("changed", []) if catalog.exists() else []
    domains = ["construcao_3d", "animacao", "terreno", "interface", "scripting", "fisica"]
    tasks=[]
    for path in changed[:80]:
        for domain in domains:
            key=f"{path}:{domain}"
            tasks.append({"id":hashlib.sha256(key.encode()).hexdigest()[:16],"fonte":path,"dominio":domain,"pedido":f"criar prototipo {domain} integrado ao módulo {path}","status":"aguarda_validacao"})
    out=GENERATED_DIR / "prototype_queue.json"
    out.write_text(json.dumps({"gerado_em":datetime.now(timezone.utc).isoformat(),"regra":"nenhum prototipo entra no treino sem validacao","tarefas":tasks},ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"[prototipos] {len(tasks)} tarefas geradas para avaliacao")
if __name__ == "__main__": main()
