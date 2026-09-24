#!/usr/bin/env python3
"""Organiza e indexa um acervo Roblox no armazenamento do usuário.

Uso no Termux/Android:
  python roblox_dataset_ingest.py /storage/emulated/0/ArkherAITraining

A conversão binário -> XML depende de um conversor Roblox instalado e
configurado em ARKHER_RBXL_CONVERTER. O script nunca finge conversão: se não
houver conversor, preserva o original e registra pendência.
"""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, subprocess, time
from pathlib import Path

EXTS={".rbxl":"rbxl", ".rbxlx":"rbxlx", ".rbxm":"rbxm", ".rbxmx":"rbxmx"}
SKIP={"_arkher",".git","node_modules"}

def digest(p):
 h=hashlib.sha256(); n=0
 with p.open("rb") as f:
  while b:=f.read(1024*1024): h.update(b); n+=len(b)
 return h.hexdigest(),n

def is_xml(p):
 try: return p.open("rb").read(200).lstrip().startswith(b"<")
 except OSError: return False

def convert(src,dst,kind):
 """Executa conversor externo com {input} e {output}; retorna motivo."""
 template=os.environ.get("ARKHER_RBXL_CONVERTER","").strip()
 if not template: return False,"conversor nao configurado"
 cmd=template.format(input=str(src),output=str(dst),kind=kind)
 try:
  r=subprocess.run(cmd,shell=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=900)
  if r.returncode==0 and dst.exists() and dst.stat().st_size>0: return True,"convertido"
  return False,(r.stdout or "falha do conversor")[-500:]
 except Exception as e: return False,str(e)

def main():
 ap=argparse.ArgumentParser(); ap.add_argument("root",type=Path); ap.add_argument("--once",action="store_true"); ap.add_argument("--interval",type=int,default=60); a=ap.parse_args()
 root=a.root.expanduser(); store=root/"_arkher"; folders={k:store/k for k in ("originais","rbxlx","rbxmx","previews","indices","pendencias")}
 for p in folders.values(): p.mkdir(parents=True,exist_ok=True)
 while True:
  records=[]
  for src in sorted(root.rglob("*")):
   if not src.is_file() or any(part in SKIP for part in src.relative_to(root).parts): continue
   kind=EXTS.get(src.suffix.lower())
   if not kind: continue
   sha,size=digest(src); rec={"arquivo":str(src),"tipo":kind,"sha256":sha,"bytes":size,"visto_em":time.time()}
   # Sempre mantém cópia original organizada, sem apagar o arquivo do usuário.
   original=folders["originais"]/f"{sha[:16]}_{src.name}"
   if not original.exists(): shutil.copy2(src,original)
   if kind in ("rbxl","rbxm"):
    target=folders["rbxlx" if kind=="rbxl" else "rbxmx"]/(src.stem+"."+kind+"x")
    if not target.exists() and is_xml(src): shutil.copy2(src,target)
    if not target.exists():
     ok,msg=convert(src,target,kind); rec["conversao"]={"ok":ok,"mensagem":msg,"destino":str(target)}
     if not ok: (folders["pendencias"]/(sha[:16]+".json")).write_text(json.dumps(rec,ensure_ascii=False,indent=2),encoding="utf-8")
    rec["xml"] = str(target) if target.exists() else None
   records.append(rec)
  manifest={"schema":"arkher-ingest-v1","root":str(root),"atualizado":time.time(),"arquivos":records,"conversor":"ARKHER_RBXL_CONVERTER"}
  (folders["indices"] / "manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
  print(f"[arkher-ingest] {len(records)} arquivos indexados; pendencias em {folders['pendencias']}",flush=True)
  if a.once: break
  time.sleep(max(5,a.interval))
if __name__=="__main__": main()
