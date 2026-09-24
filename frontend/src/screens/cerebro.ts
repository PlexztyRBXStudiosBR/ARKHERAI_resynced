// Cérebro: treino, memória neural e status do produto, numa única estação.

import { el } from "../components/ui";
import { icon } from "../components/icons";
import { t } from "../services/i18n";
import type { Ctx } from "../app/app";
import { renderTraining } from "./training";
import { renderMemory } from "./memory";

export function renderCerebro(ctx: Ctx): HTMLElement {
  const lang = ctx.store.state.settings.lang;
  const root = el("div", { class: "panel" });
  root.append(el("h1", {}, t("cerebro_title", lang)));
  root.append(el("p", { class: "dim" }, t("cerebro_hint", lang)));

  const statusCard = el("div", { class: "produto-card" });
  root.append(statusCard);
  void carregarStatus(ctx, statusCard);

  root.append(renderTraining(ctx));
  root.append(renderMemory(ctx));
  return root;
}

async function carregarStatus(ctx: Ctx, host: HTMLElement): Promise<void> {
  const lang = ctx.store.state.settings.lang;
  try {
    const st = await ctx.api.produtoStatus();
    host.textContent = "";
    const head = el("div", { class: "produto-head" });
    head.append(el("h2", {}, t("product_status", lang)));
    const frac = el("div", { class: "chip status" }, el("span", { class: "dot " + (st.prontos === st.total ? "on" : "warn") }), el("b", {}, `${st.prontos}/${st.total} ${t("ready", lang)}`));
    head.append(frac);
    host.append(head);
    const lista = el("ul", { class: "produto-lista" });
    for (const item of st.itens) {
      const li = el("li", { class: item.ok ? "ok" : "pend" });
      li.append(icon(item.ok ? "thumbUp" : "training", 14), el("b", {}, item.nome), el("span", { class: "dim" }, " — " + item.detalhe));
      lista.append(li);
    }
    host.append(lista);
    if (st.fora_do_produto_por_decisao.length > 0) {
      const fora = el("div", { class: "fora" });
      fora.append(el("b", {}, t("out_of_scope", lang)));
      for (const f of st.fora_do_produto_por_decisao) fora.append(el("p", { class: "dim" }, "• " + f));
      host.append(fora);
    }
  } catch {
    host.textContent = "";
    host.append(el("p", { class: "banner err" }, t("product_status_err", lang)));
  }
}
