#!/usr/bin/env python3
"""Nó de render 3D da rede ARKHER — executa scripts Blender headless em lote.

É aqui que a ARKHER "gera modelos, animações e texturas de verdade" usando
máquinas da rede (Kaggle, Colab, seu PC): ela escreve o script (no chat,
comando /blender), você salva em jobs/blender/, e este nó executa com Blender
real, devolvendo .glb + renders + frames.

Uso:
  python workers/render/render_node.py                       # roda jobs/blender/*.py
  python workers/render/render_node.py --script cena.py      # um arquivo só
  python workers/render/render_node.py --saida /kaggle/working/saida --zip

Blender é localizado por ARKHER_BLENDER (caminho do binário) ou `blender` no PATH.
Nos notebooks Kaggle/Colab o Blender é instalado na primeira célula.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JOBS_DIR = ROOT / "jobs" / "blender"
SAIDA_PADRAO = ROOT / "saida_render"


def encontrar_blender() -> str | None:
    import os

    env = os.environ.get("ARKHER_BLENDER", "")
    if env and Path(env).is_file():
        return env
    return shutil.which("blender")


def executar_script(binario: str, script: Path, timeout_s: int = 1800) -> tuple[bool, list[Path]]:
    """Roda um script no Blender headless. Artefatos ficam em arkher_saida/ ao lado."""
    print(f"== executando {script.name} …")
    proc = subprocess.run(
        [binario, "--background", "--python", str(script)],
        capture_output=True, text=True, timeout=timeout_s, cwd=str(script.parent),
    )
    if proc.returncode != 0:
        print(proc.stderr[-1500:] if proc.stderr else "falhou sem stderr")
        return False, []
    saida = script.parent / "arkher_saida"
    artefatos = sorted(saida.glob("*")) if saida.is_dir() else []
    print(f"   ok — {len(artefatos)} artefato(s)")
    return True, artefatos


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--script", type=Path, help="executa só este arquivo")
    ap.add_argument("--jobs-dir", type=Path, default=JOBS_DIR)
    ap.add_argument("--saida", type=Path, default=SAIDA_PADRAO)
    ap.add_argument("--zip", action="store_true", help="compacta tudo em arkher_render.zip")
    args = ap.parse_args()

    binario = encontrar_blender()
    if binario is None:
        sys.exit("Blender não encontrado. Instale-o ou defina ARKHER_BLENDER=/caminho/blender.")
    print(f"blender: {binario}")

    if args.script:
        scripts = [args.script.resolve()]
    else:
        scripts = sorted(args.jobs_dir.glob("*.py"))
    if not scripts:
        sys.exit(f"Nenhum script em {args.jobs_dir}. Peça à ARKHER: /blender cena|terreno|personagem|animacao [seed]")

    args.saida.mkdir(parents=True, exist_ok=True)
    total_ok, total_falha = 0, 0
    for script in scripts:
        try:
            ok, artefatos = executar_script(binario, script)
        except subprocess.TimeoutExpired:
            print(f"   TIMEOUT em {script.name}")
            ok, artefatos = False, []
        if not ok:
            total_falha += 1
            continue
        total_ok += 1
        destino = args.saida / script.stem
        destino.mkdir(parents=True, exist_ok=True)
        for f in artefatos:
            shutil.copy2(f, destino / f.name)

    if args.zip:
        zp = args.saida / "arkher_render.zip"
        with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(args.saida.rglob("*")):
                if f.is_file() and f.name != "arkher_render.zip":
                    z.write(f, f.relative_to(args.saida))
        print(f"zip: {zp}")

    print(f"resumo: {total_ok} ok, {total_falha} falha(s) — artefatos em {args.saida}")
    if total_falha:
        sys.exit(1)


if __name__ == "__main__":
    main()
