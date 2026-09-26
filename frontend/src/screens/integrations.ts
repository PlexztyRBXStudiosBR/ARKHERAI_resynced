// Integrações: permissões de fontes externas. O chat é a super-IA.

import { el, promptDialog, toast } from "../components/ui";
import { icon } from "../components/icons";
import { t } from "../services/i18n";
import type { Integration } from "../services/api";
import type { Ctx } from "../app/app";

export function renderIntegrations(ctx: Ctx): HTMLElement {
  const lang = ctx.store.state.settings.lang;
  const root = el("div", { class: "panel" });
  root.append(el("h1", {}, t("integrations_title", lang)));
  root.append(el("p", { class: "dim" }, t("integrations_hint", lang)));

  const grid = el("div", { class: "tools-grid" });
  root.append(grid);

  const fill = (): void => {
    void ctx.api.integrations().then((res) => {
      grid.textContent = "";
      const cats = new Map<string, Integration[]>();
      for (const it of res.integrations) {
        const list = cats.get(it.categoria) ?? [];
        list.push(it);
        cats.set(it.categoria, list);
      }
      for (const [cat, items] of cats) {
        grid.append(el("h2", { class: "integ-cat" }, cat));
        for (const c of items) grid.append(card(ctx, c, fill));
      }
    }).catch((e) => toast((e as { message?: string }).message ?? "erro"));
  };
  fill();

  return root;
}

function card(ctx: Ctx, c: Integration, refresh: () => void): HTMLElement {
  const lang = ctx.store.state.settings.lang;
  const wrap = el("div", { class: "tool-card" });
  wrap.append(
    el("h3", {}, c.nome),
    el("span", { class: "tag " + (c.authorized ? "ok" : "off") }, c.authorized ? "autorizada" : "off"),
    el("p", {}, c.descricao),
  );
  const row = el("div", { class: "row" });
  if (!c.authorized) {
    const on = el("button", { class: "pri" }, t("authorize", lang));
    on.onclick = async () => {
      let token = "";
      if (c.precisa_token) {
        const v = await promptDialog(c.token_hint || "token (opcional)", "");
        if (v === null) return;
        token = v.trim();
      }
      try {
        await ctx.api.authorizeIntegration(c.id, token);
        toast("ok");
        refresh();
      } catch (e) {
        toast((e as { message?: string }).message ?? "erro");
      }
    };
    row.append(on);
  } else {
    const off = el("button", { class: "danger" }, t("revoke", lang));
    off.onclick = async () => {
      await ctx.api.revokeIntegration(c.id);
      toast("ok");
      refresh();
    };
    row.append(off);
  }
  if (c.rota && c.arquivo) {
    const dl = el("button", { class: "ghost" });
    dl.append(icon("download", 14), " " + c.arquivo);
    dl.onclick = async () => {
      try {
        const texto = await ctx.api.getRaw(c.rota!);
        ctx.download(c.arquivo!, texto);
      } catch (e) {
        toast((e as { message?: string }).message ?? "erro");
      }
    };
    row.append(dl);
  }
  wrap.append(row);
  return wrap;
}
