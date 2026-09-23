// Tela de ferramentas: autorização, permissões, execução e histórico.

import { confirmDialog, el, toast } from "../components/ui";
import { t } from "../services/i18n";
import type { Ctx } from "../app/app";

export function renderTools(ctx: Ctx): HTMLElement {
  const s = ctx.store.state;
  const lang = s.settings.lang;
  const root = el("div", { class: "panel" });
  root.append(el("h1", {}, t("tools_title", lang)));
  const grid = el("div", { class: "tools-grid", id: "tools-grid" });
  root.append(grid);
  root.append(el("h2", {}, t("tools_history", lang)));
  const hist = el("div", { class: "tool-history", id: "tool-history" });
  root.append(hist);
  void refresh(ctx, grid, hist);
  return root;
}

async function refresh(ctx: Ctx, grid: HTMLElement, hist: HTMLElement): Promise<void> {
  const lang = ctx.store.state.settings.lang;
  try {
    const res = await ctx.api.tools();
    grid.textContent = "";
    for (const tool of res.tools) {
      const card = el("div", { class: "tool-card" });
      const status = el("span", { class: "tag " + (tool.authorized ? "ok" : "off") }, tool.authorized ? "● autorizada" : "○ sem autorização");
      card.append(el("h3", {}, tool.nome), el("p", {}, tool.descricao), status);
      const perms = el("p", { class: "dim" }, "Permissões: " + tool.permissoes.join(", "));
      card.append(perms);
      if (tool.confirmacao) card.append(el("p", { class: "dim" }, "Exige confirmação de ações."));
      const btn = el("button", { class: tool.authorized ? "danger" : "pri" }, tool.authorized ? t("revoke", lang) : t("authorize", lang));
      btn.onclick = async () => {
        if (tool.authorized) {
          if (!(await confirmDialog(t("confirm_revoke", lang), t("revoke", lang)))) return;
          await ctx.api.revokeTool(tool.id);
        } else {
          await ctx.api.authorizeTool(tool.id);
        }
        void refresh(ctx, grid, hist);
      };
      card.append(btn);
      grid.append(card);
    }
    const hres = await ctx.api.toolHistory();
    hist.textContent = "";
    if (hres.history.length === 0) {
      hist.append(el("p", { class: "dim" }, "—"));
    }
    for (const h of hres.history.slice(0, 30)) {
      hist.append(
        el(
          "div",
          { class: "hist-item" },
          `${h.created_at.slice(0, 19)} · ${h.tool_id} · ${h.ok ? "ok" : "bloqueada"} · ${h.ms}ms · ${h.arg_summary.slice(0, 60)}`,
        ),
      );
    }
  } catch (e) {
    grid.textContent = "";
    grid.append(el("p", { class: "banner err" }, (e as { message?: string }).message ?? "erro"));
    void toast("erro");
  }
}
