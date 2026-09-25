#!/usr/bin/env python3
"""Renderiza todo o acervo XML e cria um catalogo para o treino local."""
import argparse, json, subprocess, sys
from pathlib import Path
p=argparse.ArgumentParser(); p.add_argument('root',type=Path); p.add_argument('--out',type=Path,default=Path('model/datasets/generated/rbx_viewport')); a=p.parse_args(); a.out.mkdir(parents=True,exist_ok=True)
rows=[]
for f in sorted(a.root.rglob('*')):
 if f.suffix.lower() in ('.rbxlx','.rbxmx'):
  r=subprocess.run([sys.executable,str(Path(__file__).with_name('rbx_viewport.py')),str(f),'--out',str(a.out)],capture_output=True,text=True); rows.append({'arquivo':str(f),'ok':r.returncode==0,'log':r.stdout+r.stderr})
(a.out/'catalog.json').write_text(json.dumps({'schema':'arkher-viewport-v1','items':rows},ensure_ascii=False,indent=2),encoding='utf-8'); print(f'[viewport] {len(rows)} arquivos processados')
