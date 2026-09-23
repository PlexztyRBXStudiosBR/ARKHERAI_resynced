// Visualizador 3D próprio do ARKHER (WebGL puro, zero dependência externa).
// Mostra artefatos .obj gerados pela ARKHER direto na interface — a UI
// entrega 3D de verdade, não só texto.

import { el } from "./ui";
import { icon } from "./icons";

export interface ObjData {
  pos: Float32Array; // xyz por vértice
  idx: Uint32Array;  // triângulos
  altMin: number;
  altMax: number;
}

export function parseObj(texto: string): ObjData | null {
  const verts: number[] = [];
  const faces: number[] = [];
  let altMin = Infinity;
  let altMax = -Infinity;
  for (const linha of texto.split("\n")) {
    if (linha.startsWith("v ")) {
      const p = linha.trim().split(/\s+/);
      const x = parseFloat(p[1]);
      const y = parseFloat(p[2]);
      const z = parseFloat(p[3]);
      if ([x, y, z].some(Number.isNaN)) continue;
      verts.push(x, y, z);
      if (y < altMin) altMin = y;
      if (y > altMax) altMax = y;
    } else if (linha.startsWith("f ")) {
      const ids = linha.trim().split(/\s+/).slice(1).map((tk) => {
        const n = parseInt(tk.split("/")[0], 10);
        return Number.isNaN(n) ? -1 : n - 1; // OBJ é 1-indexado
      }).filter((i) => i >= 0);
      for (let i = 1; i + 1 < ids.length; i++) {
        faces.push(ids[0], ids[i], ids[i + 1]); // leque: quads e n-gons
      }
    }
  }
  if (verts.length < 9 || faces.length < 3) return null;
  return { pos: new Float32Array(verts), idx: new Uint32Array(faces), altMin, altMax };
}

const VSH = `
attribute vec3 aPos;
uniform mat4 uMvp;
uniform float uAltMin;
uniform float uAltSpan;
varying float vH;
void main() {
  vH = (aPos.y - uAltMin) / max(uAltSpan, 0.0001);
  gl_Position = uMvp * vec4(aPos, 1.0);
}`;

const FSH = `
precision mediump float;
varying float vH;
void main() {
  vec3 baixo = vec3(0.16, 0.35, 0.20);
  vec3 meio  = vec3(0.55, 0.47, 0.30);
  vec3 topo  = vec3(0.93, 0.95, 0.97);
  vec3 cor = vH < 0.5 ? mix(baixo, meio, vH * 2.0) : mix(meio, topo, (vH - 0.5) * 2.0);
  gl_FragColor = vec4(cor, 1.0);
}`;

function persp(fov: number, aspect: number, near: number, far: number): number[] {
  const f = 1 / Math.tan(fov / 2);
  return [f / aspect, 0, 0, 0, 0, f, 0, 0, 0, 0, (far + near) / (near - far), -1, 0, 0, (2 * far * near) / (near - far), 0];
}

function mul(a: number[], b: number[]): number[] {
  const r = new Array<number>(16).fill(0);
  for (let c = 0; c < 4; c++)
    for (let l = 0; l < 4; l++)
      for (let k = 0; k < 4; k++) r[c * 4 + l] += a[k * 4 + l] * b[c * 4 + k];
  return r;
}

function rotX(a: number): number[] {
  const c = Math.cos(a), s = Math.sin(a);
  return [1, 0, 0, 0, 0, c, s, 0, 0, -s, c, 0, 0, 0, 0, 1];
}
function rotY(a: number): number[] {
  const c = Math.cos(a), s = Math.sin(a);
  return [c, 0, -s, 0, 0, 1, 0, 0, s, 0, c, 0, 0, 0, 0, 1];
}
function trans(x: number, y: number, z: number): number[] {
  return [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, x, y, z, 1];
}

/** Abre o visualizador em tela cheia sobre a interface. */
export function openViewer(nome: string, conteudo: string): void {
  const dados = parseObj(conteudo);
  const overlay = el("div", { class: "viewer-overlay" });
  const head = el("div", { class: "viewer-head" });
  head.append(el("b", {}, nome));
  const fechar = el("button", { class: "mini", title: "Fechar" });
  fechar.append(icon("close", 15));
  fechar.onclick = () => overlay.remove();
  head.append(fechar);
  overlay.append(head);

  if (!dados) {
    overlay.append(el("div", { class: "viewer-erro" }, "Este arquivo não tem geometria visualizável."));
    document.body.append(overlay);
    return;
  }

  const canvas = el("canvas", { class: "viewer-canvas" }) as HTMLCanvasElement;
  overlay.append(canvas);
  overlay.append(el("div", { class: "viewer-hint" }, "arraste para orbitar"));
  document.body.append(overlay);

  const gl = canvas.getContext("webgl");
  if (!gl) {
    overlay.append(el("div", { class: "viewer-erro" }, "WebGL indisponível neste navegador."));
    return;
  }

  // normaliza para o cubo unitário centrado
  const { pos, idx, altMin, altMax } = dados;
  const centro = [0, 0, 0];
  const minB = [Infinity, Infinity, Infinity];
  const maxB = [-Infinity, -Infinity, -Infinity];
  for (let i = 0; i < pos.length; i += 3)
    for (let k = 0; k < 3; k++) {
      minB[k] = Math.min(minB[k], pos[i + k]);
      maxB[k] = Math.max(maxB[k], pos[i + k]);
    }
  for (let k = 0; k < 3; k++) centro[k] = (minB[k] + maxB[k]) / 2;
  const ext = Math.max(maxB[0] - minB[0], maxB[1] - minB[1], maxB[2] - minB[2]) || 1;
  const norm = new Float32Array(pos.length);
  for (let i = 0; i < pos.length; i += 3)
    for (let k = 0; k < 3; k++) norm[i + k] = ((pos[i + k] - centro[k]) / ext) * 2;

  const prog = gl.createProgram()!;
  for (const [tipo, src] of [[gl.VERTEX_SHADER, VSH], [gl.FRAGMENT_SHADER, FSH]] as const) {
    const sh = gl.createShader(tipo)!;
    gl.shaderSource(sh, src);
    gl.compileShader(sh);
    gl.attachShader(prog, sh);
  }
  gl.linkProgram(prog);
  gl.useProgram(prog);

  const vbo = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, vbo);
  gl.bufferData(gl.ARRAY_BUFFER, norm, gl.STATIC_DRAW);
  const aPos = gl.getAttribLocation(prog, "aPos");
  gl.enableVertexAttribArray(aPos);
  gl.vertexAttribPointer(aPos, 3, gl.FLOAT, false, 0, 0);

  const ext32 = gl.getExtension("OES_element_index_uint");
  const ibo = gl.createBuffer();
  gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, ibo);
  const idx16ok = pos.length / 3 < 65536;
  let idx16: Uint16Array | null = null;
  if (idx16ok) {
    idx16 = new Uint16Array(idx);
    gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, idx16, gl.STATIC_DRAW);
  } else if (ext32) {
    gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, idx, gl.STATIC_DRAW);
  }
  const tipoIdx = idx16ok ? gl.UNSIGNED_SHORT : gl.UNSIGNED_INT;

  const uMvp = gl.getUniformLocation(prog, "uMvp");
  const uAltMin = gl.getUniformLocation(prog, "uAltMin");
  const uAltSpan = gl.getUniformLocation(prog, "uAltSpan");
  gl.uniform1f(uAltMin, altMin);
  gl.uniform1f(uAltSpan, altMax - altMin);

  gl.enable(gl.DEPTH_TEST);
  gl.clearColor(0.04, 0.055, 0.09, 1);

  let yaw = 0.7, pitch = 0.9, dist = 3.1;
  let arrastando = false, ultimoX = 0, ultimoY = 0;

  canvas.addEventListener("pointerdown", (e) => {
    arrastando = true;
    ultimoX = e.clientX;
    ultimoY = e.clientY;
    canvas.setPointerCapture(e.pointerId);
  });
  canvas.addEventListener("pointermove", (e) => {
    if (!arrastando) return;
    yaw += (e.clientX - ultimoX) * 0.008;
    pitch = Math.min(1.45, Math.max(0.15, pitch + (e.clientY - ultimoY) * 0.006));
    ultimoX = e.clientX;
    ultimoY = e.clientY;
  });
  canvas.addEventListener("pointerup", () => (arrastando = false));
  canvas.addEventListener("pointercancel", () => (arrastando = false));
  canvas.addEventListener("wheel", (e) => {
    e.preventDefault();
    dist = Math.min(8, Math.max(1.6, dist + e.deltaY * 0.002));
  }, { passive: false });

  function desenhar(): void {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w;
      canvas.height = h;
    }
    gl!.viewport(0, 0, w, h);
    gl!.clear(gl!.COLOR_BUFFER_BIT | gl!.DEPTH_BUFFER_BIT);
    const modelo = mul(rotY(yaw), rotX(pitch));
    const vista = trans(0, 0, -dist);
    const mvp = mul(persp(0.9, w / Math.max(h, 1), 0.1, 50), mul(vista, modelo));
    gl!.uniformMatrix4fv(uMvp, false, new Float32Array(mvp));
    gl!.drawElements(gl!.TRIANGLES, idx.length, tipoIdx, 0);
    requestAnimationFrame(desenhar);
  }
  requestAnimationFrame(desenhar);
}
