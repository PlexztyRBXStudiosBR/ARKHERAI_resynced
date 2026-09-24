#!/usr/bin/env python3
"""Extrai um jogo Roblox em conhecimento estrutural compacto e rastreável."""
from __future__ import annotations
import argparse, hashlib, json, re, xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
SKIP={".git",".venv","node_modules","dist","build","__pycache__"}

def sha(p):
 h=hashlib.sha256(); n=0
 with p.open("rb") as f:
  while b:=f.read(1024*1024): h.update(b); n+=len(b)
 return h.hexdigest(),n

def safe(s): return re.sub(r"[^A-Za-z0-9_.-]+","_",s)[:100] or "unnamed"

def prop(props,name,default=""):
 x=props.get(name)
 return (x.text or default) if x is not None else default

def extract_xml(p,out):
 root=ET.parse(p).getroot(); classes=Counter(); instances=[]; scripts=[]; remotes=[]; edges=[]; attrs=[]; bindables=[]; systems=Counter()
 def walk(parent_item,parent_id="root",path=""):
  for idx,item in enumerate(parent_item.findall("Item")):
   cls=item.attrib.get("class",""); props={x.attrib.get("name",""):x for x in item.findall("Properties/*")}; name=prop(props,"Name",cls); iid=f"{parent_id}/{idx}:{safe(name)}"; full=f"{path}/{name}" if path else name
   classes[cls]+=1; systems[full.split("/")[0]]+=1
   node={"id":iid,"parent":parent_id,"path":full,"name":name,"class":cls}
   for key in ("Archivable","Disabled","RunContext","Value","PrimaryPart","Size","CFrame","Position","Color","Material","Anchored","CanCollide"):
    if key in props: node[key]=prop(props,key)
   instances.append(node); edges.append({"from":parent_id,"to":iid,"kind":"contains"})
   if cls in {"Script","LocalScript","ModuleScript"}:
    text=prop(props,"Source"); rel=Path("scripts")/(safe(name)+"_"+str(len(scripts))+".luau"); (out/rel).parent.mkdir(parents=True,exist_ok=True); (out/rel).write_text(text,encoding="utf-8")
    req=re.findall(r"require\s*\(([^\n]+)\)",text); scripts.append({"id":iid,"name":name,"class":cls,"path":str(rel),"lines":len(text.splitlines()),"requires":req,"events":re.findall(r"([A-Za-z]+):Connect\s*\(",text)})
   if cls.startswith("Remote"): remotes.append({"id":iid,"name":name,"class":cls,"path":full})
   if cls.startswith("Bindable"): bindables.append({"id":iid,"name":name,"class":cls,"path":full})
   for key,x in props.items():
    if key in {"Attributes","Tags"} or "Attribute" in key: attrs.append({"path":full,"name":key,"value":prop(props,key)})
   walk(item,iid,full)
 walk(root)
 return {"format":"rbxlx","classes":dict(classes),"instances":instances,"edges":edges,"scripts":scripts,"remotes":remotes,"bindables":bindables,"attributes":attrs,"systems":dict(systems)}

def extract(p,dest):
 digest,size=sha(p); item={"file":str(p),"sha256":digest,"bytes":size,"format":p.suffix.lower().lstrip(".")}
 if p.suffix.lower()==".rbxlx": item.update(extract_xml(p,dest)); return item
 if p.suffix.lower()==".rbxl": item.update({"format":"rbxl-binary","extractable":False,"next_step":"Studio: Save As > Roblox XML (.rbxlx)"}); return item
 if p.suffix.lower() in {".lua",".luau"}:
  text=p.read_text(encoding="utf-8",errors="replace"); item.update({"format":"luau","lines":len(text.splitlines()),"requires":re.findall(r"require\s*\(([^\n]+)\)",text)})
 return item

def main():
 ap=argparse.ArgumentParser(); ap.add_argument("source",type=Path); ap.add_argument("--out",type=Path,default=Path("model/datasets/generated/rbxl_knowledge")); a=ap.parse_args(); a.out.mkdir(parents=True,exist_ok=True)
 paths=[a.source] if a.source.is_file() else [p for p in a.source.rglob("*") if p.is_file() and p.suffix.lower() in {".rbxl",".rbxlx",".lua",".luau"} and not any(x in SKIP for x in p.parts)]
 projects=[extract(p,a.out/safe(p.stem)) for p in sorted(paths)]
 tasks=[]
 for pr in projects:
  for domain,kind in [("architecture","recreate_system"),("scripting","add_tests"),("optimization","profile_and_improve"),("integration","add_feature"),("regression","preserve_behavior")]:
   tasks.append({"id":hashlib.sha256(f"{pr['sha256']}:{domain}".encode()).hexdigest()[:16],"project":pr["file"],"domain":domain,"task":kind,"status":"aguarda_validacao"})
 manifest={"schema":"arkher-rbxl-knowledge-v2","generated_at":datetime.now(timezone.utc).isoformat(),"source":"local-user-projects","projects":projects,"progressive_tasks":tasks,"rules":["scripts extraidos nao sao executados","rbxl binario requer exportacao XML","revisar licenca e segredos","validar prototipos antes de promover"]}
 (a.out/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8"); print(f"[rbxl] {len(projects)} projetos, {len(tasks)} tarefas, saída {a.out}")
if __name__=="__main__": main()
