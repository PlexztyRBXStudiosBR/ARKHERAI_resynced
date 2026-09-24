#!/usr/bin/env python3
"""Orquestrador de treino contínuo do ARKHER.

Executa ciclos reproduzíveis e interrompíveis: preparar/validar dados, treinar
retomando o último checkpoint, avaliar e gerar relatório. Não acessa provedores
externos nem coleta dados automaticamente; novos dados precisam entrar no seed
com licença/proveniência documentada.

Uso:
  python -m model.training.auto_train                 # 24/7 até criar stop
  python -m model.training.auto_train --cycles 1      # um ciclo verificável
  touch model/checkpoints/AUTO_TRAIN_STOP             # parada segura
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from model.training.common import CHECKPOINT_DIR, ROOT, STATE_PATH, log, write_state

STOP = CHECKPOINT_DIR / "AUTO_TRAIN_STOP"
LOOP_STATE = CHECKPOINT_DIR / "auto_train_state.json"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def latest_checkpoint() -> Path | None:
    p = CHECKPOINT_DIR / "latest.pt"
    return p if p.exists() else None


def run(module: str, *args: str, logfile: Path) -> int:
    logfile.parent.mkdir(parents=True, exist_ok=True)
    with logfile.open("a", encoding="utf-8") as out:
        out.write(f"\n[{now()}] {module} {' '.join(args)}\n")
        out.flush()
        proc = subprocess.run(
            [sys.executable, "-m", module, *args], cwd=ROOT,
            stdout=out, stderr=subprocess.STDOUT,
            env={**os.environ, "PYTHONPATH": str(ROOT)},
        )
    return proc.returncode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", type=int, default=0, help="0 = contínuo; útil para serviço 24/7")
    ap.add_argument("--pause", type=int, default=30, help="segundos entre ciclos")
    ap.add_argument("--epochs", type=int, default=2)
    args = ap.parse_args()
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    state = {"status": "rodando", "inicio": now(), "ciclo": 0, "modo": "continuo" if not args.cycles else "limitado"}
    LOOP_STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    log("super mecha training iniciado; parada: " + str(STOP))
    cycle = 0
    while not STOP.exists() and (args.cycles <= 0 or cycle < args.cycles):
        cycle += 1
        tag = f"auto-c{cycle:06d}"
        logfile = CHECKPOINT_DIR / "auto_train.log"
        base = latest_checkpoint()
        state.update({"status": "ciclo", "ciclo": cycle, "tag": tag, "checkpoint_base": str(base) if base else None, "atualizado": now()})
        LOOP_STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        write_state({"status": "auto_treino", "ciclo": cycle, "tag": tag, "checkpoint_base": str(base) if base else None})

        stages: list[tuple[str, list[str]]] = [
            ("prepare", ["model.training.prepare_dataset"]),
            ("validate", ["model.training.validate_dataset"]),
        ]
        for name, cmd in stages:
            if run(cmd[0], *cmd[1:], logfile=logfile) != 0:
                state.update({"status": "erro", "etapa": name, "atualizado": now()})
                LOOP_STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
                return 2
        train_args = ["--epochs", str(args.epochs), "--tag", tag]
        if base:
            train_args += ["--resume", str(base)]
        if run("model.training.train", *train_args, logfile=logfile) != 0:
            state.update({"status": "erro", "etapa": "train", "atualizado": now()})
            LOOP_STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            return 2
        for module in ("model.training.evaluate", "model.training.report"):
            if run(module, logfile=logfile) != 0:
                log(f"aviso: {module} falhou; o checkpoint continua preservado")
        state.update({"status": "ciclo_concluido", "ultimo_checkpoint": str(latest_checkpoint()), "atualizado": now()})
        LOOP_STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        write_state({"status": "auto_ciclo_concluido", "ciclo": cycle, "checkpoint": str(latest_checkpoint()), "tag": tag})
        log(f"ciclo {cycle} concluído; checkpoint acumulado: {latest_checkpoint()}")
        if args.cycles and cycle >= args.cycles:
            break
        for _ in range(max(0, args.pause)):
            if STOP.exists():
                break
            time.sleep(1)
    state.update({"status": "parado", "motivo": "arquivo_stop" if STOP.exists() else "limite_de_ciclos", "atualizado": now()})
    LOOP_STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    write_state({"status": "auto_treino_parado", "ciclo": cycle, "motivo": state["motivo"]})
    log("super mecha training parado com segurança")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
