#!/usr/bin/env python3
"""RBXL Knowledge Extractor: transforma jogos locais em conhecimento indexável.

Suporta .rbxlx (XML) diretamente e .rbxl binário com inventário/hash honesto
(o binário precisa ser exportado pelo Studio como XML para extrair scripts).
Não executa scripts nem coloca o jogo original no Git.
"""
from __future__ import annotations
import argparse, hashlib, json, re, xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

TEXT_EXT={".luau", ".lua"}
SKIP={".git", ".venv", "node_modules", "dist", "build", "__pycache__"}

def sha(p):
    h=hashlib.sha256(); size=0
    with p.open("rb") as f:
        while b:=f.read(1024*1024): h.update(b); size+=len(b)
    return h.hexdigest(),size

def safe_name(s): return re.sub(r"[^A-Za-z0-9_.-]+","_",s)[:120] or "unnamed"

def extract_xml(p, out):
    root=ET.parse(p).getroot(); classes=Counter(); services=[]; scripts=[]; remotes=[]; instances=[]
    for item in root.findall(".//Item"):
        cls=item.attrib.get("class",""); classes[cls]+=1
        props={x.attrib.get("name",""):x for x in item.findall("Properties/*")}
        name=props.get("Name")
        n=name.text if name is not None and name.text else cls
        instances.append({"class":cls,"name":n})
        if cls in {"Script","LocalScript","ModuleScript"}:
            src=props.get("Source")
            text=src.text or "" if src is not None else ""
            rel=Path("scripts")/(safe_name(n)+"_"+str(len(scripts))+".luau")
            (out/rel).parent.mkdir(parents=True,exist_ok=True); (out/rel).write_text(text,encoding="utf-8")
            requires=re.findall(r"require\s*\(([^\n]+)\)",text)
            scripts.append({"name":n,"class":cls,"path":str(rel),"lines":len(text.splitlines()),"requires":requires})
        if cls.startswith("Remote"): remotes.append({"name":n,"class":cls})
        if cls in {"DataStoreService","ReplicatedStorage","ServerScriptService","StarterGui","Workspace"}: services.append(cls)
    return {"format":"rbxlx","classes":dict(classes),"instances":instances,"scripts":scripts,"remotes":remotes,"services":sorted(set(services))}

def extract_file(p, dest):
    digest,size=sha(p); item={"file":str(p),"sha256":digest,"bytes":size,"format":p.suffix.lower().lstrip(".")}
    if p.suffix.lower()==".rbxlx":
        item.update(extract_xml(p,dest)); return item
    if p.suffix.lower()==".rbxl":
        item.update({"format":"rbxl-binary","extractable":False,"next_step":"Studio: Save As > Roblox XML (.rbxlx)"}); return item
    if p.suffix.lower() in TEXT_EXT:
        text=p.read_text(encoding="utf-8",errors="replace")
        item.update({"format":"luau","lines":len(text.splitlines()),"requires":re.findall(r"require\s*\(([^\n]+)\)",text)})
    return item

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("source",type=Path); ap.add_argument("--out",type=Path,default=Path("model/datasets/generated/rbxl_knowledge")); args=ap.parse_args()
    src=args.source; out=args.out; out.mkdir(parents=True,exist_ok=True)
    paths=[]
    if src.is_file(): paths=[src]
    else:
        paths=[p for p in src.rglob("*") if p.is_file() and p.suffix.lower() in {".rbxl",".rbxlx",".lua",".luau"} and not any(x in SKIP for x in p.parts)]
    projects=[extract_file(p,out/safe_name(p.stem)) for p in sorted(paths)]
    manifest={"schema":"arkher-rbxl-knowledge-v1","generated_at":datetime.now(timezone.utc).isoformat(),"source":"local-user-projects","projects":projects,"rules":["scripts extraidos nao sao executados","rbxl binario requer exportacao XML","revisar licenca antes de treinar","validar prototipos antes de promover"]}
    (out/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"[rbxl] {len(projects)} arquivos indexados em {out}")
if __name__=="__main__": main()
