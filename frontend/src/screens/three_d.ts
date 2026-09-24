// Estúdio 3D: gera artefatos reais (Blender/terreno/places) e visualiza .obj na hora.

import { el, toast } from "../components/ui";
import { icon } from "../components/icons";
import { openViewer } from "../components/viewer3d";
import { t } from "../services/i18n";
import type { Ctx } from "../app/app";

interface Arquivo {
  nome: string;
  conteudo?: string;
  conteudo_b64?: string;
}

type Escolha =
  | "blender_personagem"
  | "blender_cena"
  | "blender_terreno"
  | "blender_animacao"
  | "blender_textura_pedra"
  | "blender_textura_tijolo"
  | "blender_textura_metal"
  | "blender_textura_madeira"
  | "terreno_obj"
  | "place_obby"
  | "place_arena"
  | "place_base";

const OPCOES: [Escolha, string][] = [
  ["blender_personagem", "Blender — personagem robô"],
  ["blender_cena", "Blender — cena com primitivas"],
  ["blender_terreno", "Blender — terreno heightmap"],
  ["blender_animacao", "Blender — animação + textura procedural"],
  ["blender_textura_pedra", "Blender — textura 4K pedra (tileable)"],
  ["blender_textura_tijolo", "Blender — textura 4K tijolo (tileable)"],
  ["blender_textura_metal", "Blender — textura 4K metal (tileable)"],
  ["blender_textura_madeira", "Blender — textura 4K madeira (tileable)"],
  ["terreno_obj", "Terreno .obj (visualiza em 3D aqui)"],
  ["place_obby", "Roblox Studio — obby .rbxlx"],
  ["place_arena", "Roblox Studio — arena .rbxlx"],
  ["place_base", "Roblox Studio — base .rbxlx"],
];

function toolPara(e: Escolha): { tool: string; args: (seed: number) => Record<string, unknown> } {
  if (e === "terreno_obj") return { tool: "obj_gen", args: (s) => ({ seed: String(s) }) };
  if (e.startsWith("place_")) return { tool: "rbxlx_gen", args: (s) => ({ tipo: e.slice(6), seed: String(s) }) };
  return { tool: "blender_gen", args: (s) => ({ cena: e.slice(8), seed: String(s) }) };
}

export function render3D(ctx: Ctx): HTMLElement {
  const lang = ctx.store.state.settings.lang;
  const root = el("div", { class: "panel" });
  root.append(el("h1", {}, t("three_d_title", lang)));
  root.append(el("p", { class: "dim" }, t("three_d_hint", lang)));

  const form = el("div", { class: "form3d" });
  const tipo = el("select", { class: "input" });
  for (const [v, l] of OPCOES) tipo.append(el("option", { value: v }, l));
  const seed = el("input", { class: "input", type: "number", value: "42", min: "0", max: "999999" });
  const btn = el("button", { class: "pri" });
  btn.append(icon("cube", 15), " " + t("gen", lang));
  form.append(tipo, seed, btn);
  root.append(form);

  const saida = el("div", { class: "saida3d" });
  root.append(saida);

  btn.onclick = () => void gerar();

  async function gerar(): Promise<void> {
    const e = tipo.value as Escolha;
    const s = Math.max(0, Math.min(999999, parseInt(seed.value || "42", 10) || 42));
    const { tool, args } = toolPara(e);
    saida.textContent = "";
    saida.append(el("p", { class: "typing" }, "…"));
    try {
      const r = await ctx.api.runTool(tool, args(s));
      const res = r.result as { descricao?: string; arquivo?: Arquivo };
      saida.textContent = "";
      const card = el("div", { class: "card3d" });
      card.append(el("p", {}, res.descricao ?? ""));
      const acoes = el("div", { class: "msg-actions", style: "opacity:1" });
      if (res.arquivo) {
        const dl = el("button", { class: "mini pri" });
        dl.append(icon("download", 14), " " + res.arquivo.nome);
        dl.onclick = () => ctx.download(res.arquivo!.nome, res.arquivo!.conteudo ?? "", res.arquivo!.conteudo_b64);
        acoes.append(dl);
        if (res.arquivo.nome.endsWith(".obj") && res.arquivo.conteudo) {
          const ver = el("button", { class: "mini pri" });
          ver.append(icon("cube", 14), " " + t("view_3d", lang));
          ver.onclick = () => openViewer(res.arquivo!.nome, res.arquivo!.conteudo!);
          acoes.append(ver);
        }
      }
      card.append(acoes);
      saida.append(card);
    } catch (err) {
      const e2 = err as { code?: string; message?: string };
      saida.textContent = "";
      if (e2.code === "NOT_AUTHORIZED") {
        const box = el("div", { class: "card3d" });
        box.append(el("p", {}, t("authorize_first", lang)));
        const ok = el("button", { class: "pri" }, t("authorize", lang));
        ok.onclick = async () => {
          try {
            await ctx.api.authorizeTool(tool);
            toast("ok");
            await gerar();
          } catch (er) {
            toast((er as { message?: string }).message ?? "erro");
          }
        };
        box.append(ok);
        saida.append(box);
      } else {
        saida.append(el("p", { class: "dim" }, e2.message ?? "erro"));
      }
    }
  }

  return root;
}
