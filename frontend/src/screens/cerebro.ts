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
  root.append(
    el(
      "p",
      { class: "dim" },
      "Evolução: cada 10% do produto nasce uma geração. O modelo antigo ensina o novo (copia o que couber + destila). SHA-256: amostra vista não entra de novo. Nada é copiado de IA de terceiro.",
    ),
  );

  const linCard = el("div", { class: "produto-card" });
  root.append(linCard);
  void carregarLinhagem(ctx, linCard);

  const statusCard = el("div", { class: "produto-card" });
  root.append(statusCard);
  void carregarStatus(ctx, statusCard);

  root.append(renderTraining(ctx));
  root.append(renderMemory(ctx));
  return root;
}

function fmtParams(n: number): string {
  if (n >= 1_000_000_000) return (n / 1_000_000_000).toFixed(2) + " B";
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + " M";
  return String(n);
}

async function carregarLinhagem(ctx: Ctx, host: HTMLElement): Promise<void> {
  try {
    const p = await ctx.api.linhagem();
    host.textContent = "";
    const head = el("div", { class: "produto-head" });
    head.append(el("h2", {}, "Linhagem — modelos que se ensinam"));
    head.append(el("div", { class: "chip status" }, el("span", { class: "dot " + (p.promover ? "warn" : "on") }), el("b", {}, `${p.pct}% · gen ${p.gen_atual}`)));
    host.append(head);
    host.append(
      el(
        "p",
        { class: "dim" },
        `${p.atual.nome} agora (~${fmtParams(p.atual.params_alvo)}). Próximo: ${p.proximo.nome} (~${fmtParams(p.proximo.params_alvo)}) quando o pack cruzar ${p.proximo.pct_min}%. Fórmula: ${p.formula}.`,
      ),
    );
    const lista = el("ul", { class: "produto-lista" });
    for (const it of p.barra?.itens || []) {
      const li = el("li", { class: it.ok ? "ok" : "pend" });
      li.append(el("b", {}, it.id), el("span", { class: "dim" }, ` ${it.pontos ?? it.peso}% — ${it.detalhe}`));
      lista.append(li);
    }
    host.append(lista);
    host.append(el("p", { class: "dim" }, p.promover ? "Degrau cruzado: o mini vira professor do próximo no auto-treino." : "Ainda no degrau atual — o mini continua, só com amostra nova."));
  } catch {
    host.append(el("p", { class: "dim" }, "Linhagem indisponível neste instante."));
  }
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
