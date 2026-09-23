// Tela de memória: consentimento, salvar, buscar, esquecer, exportar, apagar.

import { confirmDialog, el, toast } from "../components/ui";
import { t } from "../services/i18n";
import type { Ctx } from "../app/app";

export function renderMemory(ctx: Ctx): HTMLElement {
  const s = ctx.store.state;
  const lang = s.settings.lang;
  const root = el("div", { class: "panel" });
  root.append(el("h1", {}, t("memory_title", lang)));

  const form = el("div", { class: "memory-form" });
  const text = el("input", { class: "input", maxlength: "1000", placeholder: "Ex.: meu jogo é um plataformer 2D em pixel art" });
  const project = el("input", { class: "input", maxlength: "80", placeholder: "projeto (opcional)" });
  const consent = el("input", { type: "checkbox", id: "mem-consent" });
  const consentLabel = el("label", { class: "consent", for: "mem-consent" }, t("memory_consent", lang));
  const add = el("button", { class: "pri" }, t("memory_add", lang));
  add.onclick = async () => {
    const val = text.value.trim();
    if (!val) return;
    try {
      await ctx.api.addMemory(val, project.value.trim(), consent.checked);
      text.value = "";
      consent.checked = false;
      toast("✓");
      void refreshList(ctx, root, search.value);
    } catch (e) {
      toast((e as { message?: string }).message ?? "erro");
    }
  };
  form.append(text, project, el("div", { class: "row" }, consent, consentLabel), add);
  root.append(form);

  const search = el("input", { class: "input", placeholder: t("memory_search", lang) });
  let debounce: ReturnType<typeof setTimeout> | null = null;
  search.addEventListener("input", () => {
    if (debounce) clearTimeout(debounce);
    debounce = setTimeout(() => void refreshList(ctx, root, search.value), 250);
  });

  const ops = el("div", { class: "row" });
  const exportAll = el("button", { class: "ghost" }, t("memory_export", lang));
  exportAll.onclick = async () => {
    const res = await ctx.api.memories();
    ctx.download("arkher-memorias.json", JSON.stringify(res.memories, null, 2));
  };
  const clearAll = el("button", { class: "danger" }, t("memory_clear", lang));
  clearAll.onclick = async () => {
    if (await confirmDialog(t("confirm_memory_clear", lang), t("memory_clear", lang))) {
      await ctx.api.clearMemories();
      void refreshList(ctx, root, search.value);
    }
  };
  ops.append(search, exportAll, clearAll);
  root.append(ops);

  const list = el("div", { class: "memory-list", id: "memory-list" });
  root.append(list);
  void refreshList(ctx, root, "");
  return root;
}

async function refreshList(ctx: Ctx, root: HTMLElement, q: string): Promise<void> {
  const s = ctx.store.state;
  const lang = s.settings.lang;
  const list = root.querySelector("#memory-list");
  if (!list) return;
  try {
    const res = await ctx.api.memories(q);
    list.textContent = "";
    if (res.memories.length === 0) {
      list.append(el("p", { class: "dim" }, "—"));
      return;
    }
    for (const m of res.memories) {
      const item = el("div", { class: "memory-item" });
      const meta = el("span", { class: "dim" }, `${m.project ? "[" + m.project + "] " : ""}${m.created_at.slice(0, 10)}`);
      const forget = el("button", { class: "mini danger" }, t("memory_forget", lang));
      forget.onclick = async () => {
        await ctx.api.deleteMemory(m.id);
        void refreshList(ctx, root, q);
      };
      item.append(el("p", {}, m.text), el("div", { class: "row" }, meta, forget));
      list.append(item);
    }
  } catch (e) {
    list.textContent = "";
    list.append(el("p", { class: "banner err" }, (e as { message?: string }).message ?? "erro"));
  }
}
