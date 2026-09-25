import { el } from "../components/ui";
import type { Ctx } from "../app/app";
import { Engine } from "@babylonjs/core/Engines/engine";
import { WebGPUEngine } from "@babylonjs/core/Engines/webgpuEngine";
import { Scene } from "@babylonjs/core/scene";
import { ArcRotateCamera } from "@babylonjs/core/Cameras/arcRotateCamera";
import { Vector3 } from "@babylonjs/core/Maths/math.vector";
import { Color3 } from "@babylonjs/core/Maths/math.color";
import { HemisphericLight } from "@babylonjs/core/Lights/hemisphericLight";
import { MeshBuilder } from "@babylonjs/core/Meshes/meshBuilder";
import { StandardMaterial } from "@babylonjs/core/Materials/standardMaterial";

export function renderRender(_ctx: Ctx): HTMLElement {
  const root=el("div",{class:"panel"}); root.append(el("h1",{},"Render"),el("p",{class:"dim"},"Babylon.js + WebGPU (WebGL2 fallback). Carregue rbxlx/rbxmx para visualizar a cena."));
  const input=el("input",{type:"file",class:"input",accept:".rbxlx,.rbxmx,.xml"}) as HTMLInputElement;
  const canvas=el("canvas",{class:"render-canvas"}) as HTMLCanvasElement; canvas.style.width="100%"; canvas.style.height="600px"; canvas.style.background="#101820";
  const status=el("p",{class:"dim"},"Aguardando arquivo..."); root.append(input,status,canvas);
  input.onchange=()=>{const f=input.files?.[0];if(f){status.textContent="Carregando Babylon/WebGPU...";void f.text().then(x=>loadScene(x,canvas,status));}}; return root;
}
async function loadScene(xml:string,canvas:HTMLCanvasElement,status:HTMLElement){
  let engine: Engine | WebGPUEngine;
  if (typeof navigator !== "undefined" && "gpu" in navigator) { const e=new WebGPUEngine(canvas,{antialias:true}); await e.initAsync(); engine=e; status.textContent="WebGPU ativo"; }
  else { engine=new Engine(canvas,true,{preserveDrawingBuffer:true,stencil:true}); status.textContent="WebGPU indisponível; WebGL2 ativo"; }
  const scene=new Scene(engine); scene.clearColor=new Color3(0.025,0.04,0.07).toColor4(1); const cam=new ArcRotateCamera("camera",-Math.PI/2,Math.PI/3,80,Vector3.Zero(),scene); cam.attachControl(canvas,true); new HemisphericLight("sun",new Vector3(0.2,1,0.3),scene);
  const doc=new DOMParser().parseFromString(xml,"text/xml"); const items=[...doc.querySelectorAll("Item")].filter(x=>["Part","MeshPart","WedgePart","UnionOperation","SpawnLocation"].includes(x.getAttribute("class")||""));
  const nums=(n:Element|null)=>n?((n.textContent||"").match(/[-+]?\d*\.?\d+/g)||[]).map(Number):[0,0,0];
  items.slice(0,10000).forEach((it,i)=>{const p=nums(it.querySelector('Properties > Vector3[name="Position"]'));const s=nums(it.querySelector('Properties > Vector3[name="Size"]'));const box=MeshBuilder.CreateBox("Instance_"+i,{width:Math.max(.1,s[0]||4),height:Math.max(.1,s[1]||1),depth:Math.max(.1,s[2]||4)},scene);box.position=new Vector3(p[0]||0,p[1]||0,p[2]||0);const m=new StandardMaterial("mat_"+i,scene);m.diffuseColor=Color3.FromHSV((i*0.071)%1,.55,.8);box.material=m;});
  if(items.length) cam.target=new Vector3(0,0,0); engine.runRenderLoop(()=>scene.render()); window.addEventListener("resize",()=>engine.resize()); status.textContent+=` • ${items.length} objetos carregados`;
}
