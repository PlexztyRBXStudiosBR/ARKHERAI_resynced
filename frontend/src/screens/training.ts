// Aba de treinamento: gráficos reais do treino no servidor, atualizados
// somente quando o usuário aperta o botão Atualizar (sem consulta automática).

import { confirmDialog, el, toast } from "../components/ui";
import { t } from "../services/i18n";
import type { Ctx } from "../app/app";

const STEPS: { id: string; nome: string }[] = [
  { id: "prepare", nome: "1. Preparar dataset" },
  { id: "validate", nome: "2. Validar dataset" },
  { id: "tokenizer", nome: "3. Treinar tokenizer" },
  { id: "init", nome: "4. Inicializar pesos" },
  { id: "train", nome: "5. Treinar (épocas)" },
  { id: "evaluate", nome: "6. Avaliar perda" },
  { id: "report", nome: "7. Relatório" },
];

export function renderTraining(ctx: Ctx): HTMLElement {
  const s = ctx.store.state;
  const lang = s.settings.lang;
  const root = el("div", { class: "panel" });
  root.append(el("h1", {}, t("training_title", lang)));
  root.append(el("p", { class: "dim" }, t("training_note", lang)));

  const topbar = el("div", { class: "row" });
  const refreshBtn = el("button", { class: "pri" }, "⟳ " + t("training_refresh", lang));
  refreshBtn.onclick = () => void refresh(ctx, statusBox, chartBox, logBox);
  topbar.append(refreshBtn);
  root.append(topbar);

  const statusBox = el("div", { class: "train-status" });
  const chartBox = el("div", { class: "train-chart" });
  root.append(statusBox);
  root.append(el("h2", {}, t("training_loss", lang)));
  root.append(chartBox);

  root.append(el("h2", {}, "Etapas"));
  const steps = el("div", { class: "steps" });
  for (const st of STEPS) {
    const b = el("button", { class: "ghost" }, st.nome + " — " + t("training_start", lang));
    b.onclick = async () => {
      if (!(await confirmDialog(t("confirm_training", lang), t("training_start", lang)))) return;
      try {
        await ctx.api.trainingStart(st.id);
        toast("▶ " + st.nome);
        setTimeout(() => void refresh(ctx, statusBox, chartBox, logBox), 1200);
      } catch (e) {
        toast((e as { message?: string }).message ?? "erro");
      }
    };
    steps.append(b);
  }
  root.append(steps);

  const logBox = el("pre", { class: "train-log" }, "");
  root.append(logBox);
  void refresh(ctx, statusBox, chartBox, logBox);
  return root;
}

async function refresh(ctx: Ctx, statusBox: HTMLElement, chartBox: HTMLElement, logBox: HTMLElement): Promise<void> {
  try {
    const res = await ctx.api.trainingStatus();
    statusBox.textContent = "";
    const st = res.state;
    const job = res.job;
    const linhas: string[] = [];
    linhas.push(`Estado: ${st.status}`);
    if (st.epoch) linhas.push(`Época: ${st.epoch}/${st.epochs_alvo ?? "?"}`);
    if (st.passo) linhas.push(`Passo: ${st.passo}`);
    if (st.perda_media) linhas.push(`Perda média: ${st.perda_media}`);
    if (st.perda_final_validacao) linhas.push(`Perda validação (final): ${st.perda_final_validacao}`);
    if (st.versao) linhas.push(`Checkpoint: ${st.versao}`);
    if (job) linhas.push(`Trabalho: ${job.step} ${job.running ? "(rodando)" : `(fim, código ${job.exit_code ?? "?"})`}`);
    statusBox.append(el("p", {}, linhas.join("  ·  ")));

    // gráfico SVG real da perda
    chartBox.textContent = "";
    const perda = st.perda ?? [];
    if (perda.length >= 2) {
      chartBox.append(lossChart(perda));
    } else {
      chartBox.append(el("p", { class: "dim" }, "Sem registros de perda ainda."));
    }

    const logRes = await ctx.api.trainingStatus(); // estado já inclui origem
    void logRes;
    const lines = await fetchLog(ctx);
    logBox.textContent = lines.slice(-14).join("\n");
  } catch (e) {
    statusBox.textContent = "";
    statusBox.append(el("p", { class: "banner err" }, (e as { message?: string }).message ?? "erro"));
  }
}

async function fetchLog(ctx: Ctx): Promise<string[]> {
  try {
    const res = await fetch(`${ctx.base()}/api/training/log?step=train`, {
      headers: ctx.store.state.token ? { Authorization: `Bearer ${ctx.store.state.token}` } : {},
    });
    const data = (await res.json()) as { lines?: string[] };
    return data.lines ?? [];
  } catch {
    return [];
  }
}

function lossChart(perda: number[]): SVGElement {
  const w = 640;
  const h = 160;
  const pad = 18;
  const max = Math.max(...perda);
  const min = Math.min(...perda);
  const range = Math.max(1e-6, max - min);
  const pts = perda
    .map((v, i) => {
      const x = pad + (i * (w - 2 * pad)) / Math.max(1, perda.length - 1);
      const y = h - pad - ((v - min) / range) * (h - 2 * pad);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  svg.setAttribute("class", "loss-svg");
  const poly = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
  poly.setAttribute("points", pts);
  poly.setAttribute("fill", "none");
  poly.setAttribute("stroke", "var(--acc)");
  poly.setAttribute("stroke-width", "2");
  svg.append(poly);
  const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
  label.setAttribute("x", String(pad));
  label.setAttribute("y", "14");
  label.setAttribute("fill", "var(--dim)");
  label.setAttribute("font-size", "11");
  label.textContent = `min ${min.toFixed(3)} · máx ${max.toFixed(3)}`;
  svg.append(label);
  return svg;
}
