// Configurações: preferências, estado do modelo, dados, diagnóstico e logs.

import { confirmDialog, el, toast } from "../components/ui";
import { t } from "../services/i18n";
import type { Ctx } from "../app/app";

export function renderSettings(ctx: Ctx): HTMLElement {
  const s = ctx.store.state;
  const lang = s.settings.lang;
  const root = el("div", { class: "panel" });
  root.append(el("h1", {}, t("settings_title", lang)));

  const grid = el("div", { class: "settings-grid" });

  // nome
  const name = el("input", { class: "input", maxlength: "60", value: s.settings.userName, placeholder: t("settings_user", lang) });
  name.addEventListener("change", () => ctx.store.updateSettings({ userName: name.value.trim() }));
  grid.append(field(t("settings_user", lang), name));

  // idioma
  const langSel = el("select", { class: "input" });
  for (const [v, lbl] of [["pt-BR", "Português (Brasil)"], ["en", "English"]] as const) {
    const opt = el("option", { value: v }, lbl);
    if (s.settings.lang === v) opt.selected = true;
    langSel.append(opt);
  }
  langSel.addEventListener("change", () => ctx.store.updateSettings({ lang: langSel.value as "pt-BR" | "en" }));
  grid.append(field(t("settings_lang", lang), langSel));

  // tema
  const themeSel = el("select", { class: "input" });
  for (const [v, lbl] of [["dark", t("theme_dark", lang)], ["light", t("theme_light", lang)]] as const) {
    const opt = el("option", { value: v }, lbl);
    if (s.settings.theme === v) opt.selected = true;
    themeSel.append(opt);
  }
  themeSel.addEventListener("change", () => ctx.store.updateSettings({ theme: themeSel.value as "dark" | "light" }));
  grid.append(field(t("settings_theme", lang), themeSel));

  // fonte
  const fontSel = el("select", { class: "input" });
  for (const [v, lbl] of [["0.85", "Pequena"], ["1", "Normal"], ["1.15", "Grande"]] as const) {
    const opt = el("option", { value: v }, lbl);
    if (String(s.settings.fontScale) === v) opt.selected = true;
    fontSel.append(opt);
  }
  fontSel.addEventListener("change", () => ctx.store.updateSettings({ fontScale: Number(fontSel.value) }));
  grid.append(field(t("settings_font", lang), fontSel));

  // memória
  const memToggle = checkbox(t("settings_memory", lang), s.settings.memoryEnabled, (v) => ctx.store.updateSettings({ memoryEnabled: v }));
  grid.append(memToggle);

  // modo seguro
  const safeToggle = checkbox(t("settings_safe", lang), s.settings.safeMode, (v) => ctx.store.updateSettings({ safeMode: v }));
  grid.append(safeToggle);

  // backend
  const backend = el("input", { class: "input", value: s.settings.backendBase, placeholder: "https://backend.arkher.exemplo (vazio = mesmo servidor)" });
  backend.addEventListener("change", () => ctx.store.updateSettings({ backendBase: backend.value.trim() }));
  grid.append(field(t("settings_backend", lang), backend));

  root.append(grid);

  // estado do modelo (real)
  const modelBox = el("div", { class: "model-box" });
  modelBox.append(el("h2", {}, t("settings_model", lang)));
  const modelInfo = el("div", { class: "dim" }, "…");
  modelBox.append(modelInfo);
  root.append(modelBox);
  void ctx.api.modelStatus().then((m) => {
    modelInfo.textContent = "";
    const linhas = [
      `Estado: ${m.state}`,
      m.checkpoint_version ? `Checkpoint: ${m.checkpoint_version}` : "",
      m.parameters ? `Parâmetros: ${m.parameters.toLocaleString()}` : "",
      m.device ? `Dispositivo: ${m.device}` : "",
      m.quality ? `Qualidade: ${m.quality}` : "",
      m.error ? `Erro: ${m.error}` : "",
    ].filter(Boolean);
    modelInfo.append(el("p", {}, linhas.join(" · ")));
  }).catch(() => (modelInfo.textContent = t("err_backend", lang)));

  // versão
  root.append(el("p", { class: "dim" }, `${t("settings_version", lang)}: ${ctx.version ?? "…"}`));

  // dados
  const dataRow = el("div", { class: "row" });
  const exportBtn = el("button", { class: "ghost" }, t("settings_export", lang));
  exportBtn.onclick = async () => {
    try {
      const res = await ctx.api.runTool("data_export", {});
      ctx.download("arkher-dados.json", JSON.stringify(res.result, null, 2));
    } catch (e) {
      toast((e as { message?: string }).message ?? "erro — autorize a ferramenta data_export");
    }
  };
  const wipe = el("button", { class: "danger" }, t("settings_wipe", lang));
  wipe.onclick = async () => {
    if (!(await confirmDialog(t("confirm_wipe", lang), t("settings_wipe", lang)))) return;
    try {
      const sessions = await ctx.api.sessions();
      for (const sess of sessions.sessions) await ctx.api.deleteSession(sess.id);
      await ctx.api.clearMemories();
      ctx.store.set({ sessions: [], messages: [], currentSessionId: null });
      toast("✓");
    } catch (e) {
      toast((e as { message?: string }).message ?? "erro");
    }
  };
  dataRow.append(exportBtn, wipe);
  root.append(dataRow);

  // diagnóstico
  root.append(el("h2", {}, t("settings_diag", lang)));
  const diag = el("pre", { class: "diag" }, "…");
  const diagBtn = el("button", { class: "ghost" }, "▶ " + t("settings_diag", lang));
  diagBtn.onclick = async () => {
    try {
      const d = await ctx.api.diagnostics();
      diag.textContent = JSON.stringify(d, null, 2);
    } catch (e) {
      diag.textContent = t("err_backend", lang);
    }
  };
  root.append(diagBtn, diag);

  // logs locais
  root.append(el("h2", {}, t("settings_logs", lang)));
  const logs = el("pre", { class: "diag" }, s.localLogs.join("\n") || "—");
  root.append(logs);

  return root;
}

function field(label: string, control: HTMLElement): HTMLElement {
  const wrap = el("label", { class: "field" });
  wrap.append(el("span", {}, label), control);
  return wrap;
}

function checkbox(label: string, checked: boolean, onChange: (v: boolean) => void): HTMLElement {
  const id = "cb_" + Math.random().toString(36).slice(2, 8);
  const wrap = el("label", { class: "field row", for: id });
  const cb = el("input", { type: "checkbox", id });
  cb.checked = checked;
  cb.addEventListener("change", () => onChange(cb.checked));
  wrap.append(cb, el("span", {}, label));
  return wrap;
}
