// Abas de produção: cada uma gera artefato real (Luau, rbxlx, rbxmx, PNG, py).

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

interface TabCat {
  id: string;
  nome: Record<string, string>;
  hint: Record<string, string>;
  receitas: [string, string][];
}

const cache = new Map<string, TabCat>();

export function renderStudio(ctx: Ctx, tabId: string): HTMLElement {
  const lang = ctx.store.state.settings.lang;
  const root = el("div", { class: "panel studio-panel" });
  const head = el("div", { class: "produto-head" });
  head.append(el("h1", {}, tabId));
  root.append(head);
  const hint = el("p", { class: "dim" }, "…");
  root.append(hint);

  const form = el("div", { class: "form3d" });
  const sel = el("select", { class: "input" }) as HTMLSelectElement;
  const seed = el("input", { class: "input", type: "number", value: "42", min: "0", max: "999999" }) as HTMLInputElement;
  const extra = el("input", { class: "input", placeholder: t("three_d_extra", lang), maxlength: "200" }) as HTMLInputElement;
  const btn = el("button", { class: "pri" });
  btn.append(icon("cube", 15), " " + t("gen", lang));
  const sendVm = el("button", { class: "ghost" }, "Mandar ao Workspace");
  form.append(sel, seed, extra, btn, sendVm);
  root.append(form);
  const saida = el("div", { class: "saida3d" });
  root.append(saida);

  let last: { arquivo?: Arquivo; descricao?: string } | null = null;

  void ctx.api.studioCatalog().then((res) => {
    const cat = (res.tabs as TabCat[]).find((x) => x.id === tabId);
    if (!cat) {
      hint.textContent = "aba desconhecida";
      return;
    }
    cache.set(tabId, cat);
    const nome = cat.nome[lang] || cat.nome["pt-BR"] || tabId;
    head.querySelector("h1")!.textContent = nome;
    hint.textContent = cat.hint[lang] || cat.hint["pt-BR"] || "";
    sel.textContent = "";
    for (const [id, lab] of cat.receitas) sel.append(el("option", { value: id }, lab));
  }).catch((e) => {
    hint.textContent = (e as { message?: string }).message ?? "erro";
  });

  btn.onclick = async () => {
    saida.textContent = "";
    saida.append(el("p", { class: "typing" }, "gerando…"));
    try {
      const r = await ctx.api.studioGenerate(tabId, sel.value, Number(seed.value) || 42, extra.value.trim());
      const res = r.result as { descricao?: string; arquivo?: Arquivo; como_usar?: string };
      last = res;
      saida.textContent = "";
      const card = el("div", { class: "card3d" });
      card.append(el("p", {}, res.descricao ?? ""));
      if (res.como_usar) card.append(el("p", { class: "dim" }, res.como_usar));
      const acoes = el("div", { class: "row" });
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
        if (res.arquivo.nome.toLowerCase().endsWith(".png") && res.arquivo.conteudo_b64) {
          card.append(el("img", { class: "tex-preview", alt: res.arquivo.nome, src: "data:image/png;base64," + res.arquivo.conteudo_b64 }));
        }
        if (res.arquivo.conteudo && /\.(lua|py|md|json|yml|gdshader)$/i.test(res.arquivo.nome)) {
          const pre = el("pre", { class: "train-log" }, res.arquivo.conteudo.slice(0, 4000));
          card.append(pre);
        }
      }
      card.append(acoes);
      saida.append(card);
    } catch (err) {
      saida.textContent = "";
      saida.append(el("p", { class: "banner err" }, (err as { message?: string }).message ?? "erro"));
    }
  };

  sendVm.onclick = async () => {
    if (!last?.arquivo) {
      toast("Gere antes");
      return;
    }
    try {
      const vms = await ctx.api.workspaceList();
      const vm = vms.vms[0];
      if (!vm) {
        toast("Cadastre um PC no Workspace");
        return;
      }
      const arq = last.arquivo;
      const sync = await ctx.api.workspaceJob(vm.id, "sync_file", {
        nome: arq.nome,
        conteudo: arq.conteudo ?? "",
        conteudo_b64: arq.conteudo_b64 ?? "",
      });
      const path = (sync.result as { path?: string } | undefined)?.path;
      if (path && /\.(rbxlx|rbxmx)$/i.test(arq.nome)) {
        await ctx.api.workspaceJob(vm.id, "import_place", { path });
      }
      toast("enviado ao PC");
    } catch (e) {
      toast((e as { message?: string }).message ?? "erro");
    }
  };

  return root;
}
