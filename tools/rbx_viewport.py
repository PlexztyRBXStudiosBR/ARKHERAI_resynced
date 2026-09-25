#!/usr/bin/env python3
"""Viewport offline aproximado para rbxlx/rbxmx, sem Roblox Studio.
Gera SVG/HTML/JSON: geometria, hierarquia, materiais e scripts indexados."""
from __future__ import annotations
import argparse, html, json, math, re, xml.etree.ElementTree as ET
from pathlib import Path

def val(props,k,default=""):
 x=props.get(k); return (x.text or default) if x is not None else default

def vec(s):
 m=re.findall(r"[-+]?\d*\.?\d+",s or "")
 return tuple(float(x) for x in m[:3]) if len(m)>=3 else (0.,0.,0.)
def color(s):
 v=vec(s)
 if max(v)<=1 and max(v)>0: v=tuple(x*255 for x in v)
 return "#%02x%02x%02x"%tuple(max(0,min(255,int(x))) for x in (v or (120,150,180)))

def scan(path):
 root=ET.parse(path).getroot(); nodes=[]
 def walk(parent,prefix="",depth=0):
  for i,it in enumerate(parent.findall("Item")):
   cls=it.get("class",""); ps={x.get("name",""):x for x in it.findall("Properties/*")}; name=val(ps,"Name",cls); pos=vec(val(ps,"Position") or val(ps,"CFrame")); size=vec(val(ps,"Size")) or (4.,1.,4.); node={"id":f"{prefix}/{i}","name":name,"class":cls,"path":(prefix+"/"+name).strip("/"),"position":pos,"size":size,"color":color(val(ps,"Color")),"material":val(ps,"Material"),"anchored":val(ps,"Anchored"),"children":[]}
   nodes.append(node); walk(it,node["id"],depth+1)
 walk(root); return nodes

def render(nodes,w=1200,h=760):
 geom=[n for n in nodes if n["class"] in {"Part","MeshPart","WedgePart","CornerWedgePart","TrussPart","UnionOperation","SpawnLocation"}]
 if not geom: geom=nodes[:300]
 xs=[n["position"][0] for n in geom] or [0]; zs=[n["position"][2] for n in geom] or [0]; minx,maxx=min(xs),max(xs); minz,maxz=min(zs),max(zs); sx=max(1,maxx-minx); sz=max(1,maxz-minz); scale=min((w-100)/sx,(h-130)/sz)
 def xy(n): return (50+(n["position"][0]-minx)*scale, h-70-(n["position"][2]-minz)*scale)
 parts=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}"><rect width="100%" height="100%" fill="#101820"/><text x="24" y="32" fill="#e4b537" font-family="monospace" font-size="20">ARKHER VIEWPORT • {len(nodes)} INSTANCES</text><text x="24" y="55" fill="#9aa7ad" font-family="monospace" font-size="12">render estrutural aproximado • rbxlx/rbxmx</text><g stroke="#263640" stroke-width="1">']
 for n in geom[:3000]:
  x,y=xy(n); sw=max(3,min(80,abs(n["size"][0])*scale)); sh=max(3,min(80,abs(n["size"][2])*scale)); parts.append(f'<rect x="{x-sw/2:.1f}" y="{y-sh/2:.1f}" width="{sw:.1f}" height="{sh:.1f}" fill="{n["color"]}" fill-opacity=".82"><title>{html.escape(n["path"])} | {html.escape(n["class"])} | {html.escape(n["material"])}</title></rect>')
 parts.append('</g></svg>'); return ''.join(parts)

def main():
 ap=argparse.ArgumentParser(); ap.add_argument("input",type=Path); ap.add_argument("--out",type=Path,default=Path("model/datasets/generated/rbx_viewport")); a=ap.parse_args(); a.out.mkdir(parents=True,exist_ok=True)
 nodes=scan(a.input); base=a.out/a.input.stem; svg=render(nodes); (base.with_suffix('.svg')).write_text(svg,encoding='utf-8'); (base.with_suffix('.json')).write_text(json.dumps({"source":str(a.input),"nodes":nodes},ensure_ascii=False,indent=2),encoding='utf-8');
 tree=''.join(f'<li><b>{html.escape(n["class"])}</b> {html.escape(n["path"])} — {html.escape(n["material"])} </li>' for n in nodes[:5000]); (base.with_suffix('.html')).write_text(f'<!doctype html><meta charset="utf-8"><title>ARKHER viewport</title><style>body{{background:#101820;color:#ddd;font:13px monospace;display:flex;gap:20px}}svg{{width:70vw;border:1px solid #d4a932}}aside{{max-height:95vh;overflow:auto}}</style>{svg}<aside><h3>Explorer ({len(nodes)})</h3><ul>{tree}</ul></aside>',encoding='utf-8'); print(f"[viewport] {len(nodes)} instances -> {base}.svg/.html/.json")
if __name__=='__main__': main()
