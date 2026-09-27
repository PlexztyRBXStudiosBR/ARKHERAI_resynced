// Vault: Godot + Roblox + Blender + o que o pack gerou. Sem retrenar o mesmo hash.

import { el, toast } from "../components/ui";
import { icon } from "../components/icons";
import type { Ctx } from "../app/app";

type Item = { nome: string; pasta: string; bytes: number; tipo: string; path?: string };

export function renderVault(ctx: Ctx): HTMLElement {
  const root = el("div", { class: "panel" });
  root.append(el("h1", {}, "Vault"));
  root.append(
    el(
      "p",
      { class: "dim" },
      "Motor principal Godot (.tscn .gd project.godot). Roblox (.rbxlx .lua) e Blender (.py) continuam aqui. Versão sua + versão de treino.",
    ),
  );
  const status = el("p", { class: "dim" }, "carregando…");
  const list = el("div", { class: "tools-grid" });
  root.append(status, list);

  void (async () => {
    try {
      const res = await ctx.api.studioVault();
      const itens = (res.itens || []) as Item[];
      status.textContent = itens.length
        ? `${itens.length} no cofre`
        : "Vault vazio — gere na aba Godot (ou Places/Blender). O pack Android entra em Ingerir.";
      list.textContent = "";
      for (const it of itens) {
        const card = el("div", { class: "tool-card" });
        card.append(
          el("h3", {}, it.nome),
          el("p", { class: "dim" }, `${it.pasta} · ${it.tipo} · ${it.bytes} bytes`),
        );
        if (it.path) {
          const dl = el("button", { class: "mini" }, "abrir");
          dl.onclick = async () => {
            try {
              const r = await ctx.api.vaultItem(it.path!);
              ctx.download(r.nome || it.nome, r.conteudo || "");
            } catch (e) {
              toast((e as { message?: string }).message ?? "erro");
            }
          };
          card.append(dl);
        }
        list.append(card);
      }
    } catch (e) {
      status.textContent =
        "Vault precisa do PC ligado (Tailscale + senha no Workspace). " +
        ((e as { message?: string }).message ?? "backend offline");
    }
  })();

  const acervo = el("div", { class: "produto-card" });
  acervo.append(
    el("h2", {}, "Acervo"),
    el("p", { class: "dim" }, "Celular: /storage/emulated/0/ArkherAITraining — XML rbxmx/rbxlx + o que for Godot no pack."),
  );
  const b = el("button", { class: "pri" });
  b.append(icon("download", 14), " Ingerir acervo");
  b.onclick = async () => {
    try {
      const r = await ctx.api.acervoIngest();
      toast(`rbxlx=${String(r["xml_rbxlx"] ?? 0)} rbxmx=${String(r["xml_rbxmx"] ?? 0)}`);
    } catch (e) {
      toast((e as { message?: string }).message ?? "erro");
    }
  };
  const cicloBtn = el("button", { class: "ghost" });
  cicloBtn.append(icon("training", 14), " Ciclo do pack (520 / +100MB)");
  const paramsBox = el("p", { class: "dim" }, "Parâmetros: rode o ciclo para contar no fim.");
  cicloBtn.onclick = async () => {
    try {
      const r = (await ctx.api.acervoCiclo()) as {
        analise?: { vistos?: number; novos?: number; pulados_hash?: number; gigantes_100mb?: number };
        parametros?: { params_agora?: number; params_proximo?: number; nome?: string; proximo_nome?: string; pct?: number; gen_atual?: number };
      };
      const a = r.analise || {};
      const p = r.parametros || {};
      toast(`vistos=${a.vistos ?? 0} novos=${a.novos ?? 0} pulados=${a.pulados_hash ?? 0} ≥100MB=${a.gigantes_100mb ?? 0}`);
      paramsBox.textContent =
        `Parâmetros agora: ${(p.params_agora ?? 0).toLocaleString()} (${p.nome ?? "mini"}, gen ${p.gen_atual ?? 2}, ${p.pct ?? 0}%). ` +
        `Próximo: ${p.proximo_nome ?? "midi"} ~${(p.params_proximo ?? 0).toLocaleString()}.`;
    } catch (e) {
      toast((e as { message?: string }).message ?? "erro");
    }
  };
  acervo.append(b, cicloBtn, paramsBox);
  root.append(acervo);
  return root;
}
