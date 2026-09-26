// Cockpit: tela da VM + chat de comandos ao lado.

import { confirmDialog, el, toast } from "../components/ui";
import { icon } from "../components/icons";
import { t } from "../services/i18n";
import { renderMarkdown } from "../app/md";
import type { Vm } from "../services/api";
import type { Ctx } from "../app/app";

let liveGen = 0;
let selectedId: string | null = null;
const log: { role: "user" | "assistant"; content: string }[] = [];

export function stopWorkspaceLive(): void {
  liveGen += 1;
}

export function renderWorkspace(ctx: Ctx): HTMLElement {
  const lang = ctx.store.state.settings.lang;
  const root = el("div", { class: "ws-cockpit" });
  const desk = el("div", { class: "ws-desk" });
  const side = el("div", { class: "ws-pilot" });
  root.append(desk, side);

  const bar = el("div", { class: "ws-bar" });
  const sel = el("select", { class: "input" }) as HTMLSelectElement;
  const liveBtn = el("button", { class: "pri" }, "Tela ao vivo");
  const addBtn = el("button", { class: "ghost" }, t("workspace_add", lang));
  bar.append(sel, liveBtn, addBtn);
  const screen = el("div", { class: "ws-screen" });
  const img = el("img", { alt: "tela da VM", class: "ws-frame" }) as HTMLImageElement;
  const placeholder = el("p", { class: "dim ws-ph" }, "Conecte um PC (Tailscale) para ver a tela aqui.");
  screen.append(placeholder);
  desk.append(bar, screen);

  const setup = el("div", { class: "ws-setup" });
  setup.append(formAdd(ctx, () => void refreshVms()));
  desk.append(setup);

  async function refreshVms(): Promise<void> {
    sel.textContent = "";
    try {
      const res = await ctx.api.workspaceList();
      if (!res.vms.length) {
        sel.append(el("option", { value: "" }, t("workspace_empty", lang)));
        return;
      }
      for (const vm of res.vms) {
        const o = el("option", { value: vm.id }, `${vm.name} · ${vm.tailscale_ip} · ${vm.status}`);
        if (vm.id === selectedId) o.setAttribute("selected", "true");
        sel.append(o);
      }
      if (!selectedId) selectedId = res.vms[0].id;
      sel.value = selectedId;
    } catch (e) {
      toast((e as { message?: string }).message ?? "erro");
    }
  }

  sel.onchange = () => {
    selectedId = sel.value || null;
  };

  liveBtn.onclick = () => {
    if (!selectedId) {
      toast("Cadastre um PC");
      return;
    }
    startLive(ctx, selectedId, img, screen, placeholder);
  };

  img.onclick = async (ev) => {
    if (!selectedId) return;
    const r = img.getBoundingClientRect();
    const x = Math.round(((ev.clientX - r.left) / r.width) * 1920);
    const y = Math.round(((ev.clientY - r.top) / r.height) * 1080);
    try {
      await ctx.api.workspaceJob(selectedId, "click", { x, y });
      toast(`click ${x},${y}`);
    } catch (e) {
      toast((e as { message?: string }).message ?? "erro");
    }
  };

  addBtn.onclick = () => setup.classList.toggle("on");

  side.append(pilotChat(ctx, () => selectedId));
  void refreshVms().then(() => {
    if (selectedId) startLive(ctx, selectedId, img, screen, placeholder);
  });
  return root;
}

function startLive(ctx: Ctx, vmId: string, img: HTMLImageElement, screen: HTMLElement, ph: HTMLElement): void {
  const my = ++liveGen;
  const tick = async () => {
    if (my !== liveGen) return;
    try {
      const s = await ctx.api.workspaceScreen(vmId);
      const b64 = (s as { b64?: string }).b64;
      if (b64) {
        img.src = "data:image/jpeg;base64," + b64;
        if (!img.isConnected) screen.append(img);
        ph.remove();
      } else {
        ph.textContent = (s as { message?: string }).message ?? "sem frame";
        if (!ph.isConnected) screen.append(ph);
      }
    } catch (e) {
      ph.textContent = (e as { message?: string }).message ?? "agente offline";
      if (!ph.isConnected) screen.append(ph);
    }
    if (my === liveGen) setTimeout(tick, 1600);
  };
  void tick();
}

function formAdd(ctx: Ctx, after: () => void): HTMLElement {
  const lang = ctx.store.state.settings.lang;
  const box = el("div", { class: "memory-form" });
  const name = el("input", { class: "input", placeholder: t("workspace_name", lang), maxlength: "60" }) as HTMLInputElement;
  name.value = "PC virtual";
  const ip = el("input", { class: "input", placeholder: t("workspace_ip", lang), maxlength: "45" }) as HTMLInputElement;
  const user = el("input", { class: "input", placeholder: t("workspace_user", lang), maxlength: "80" }) as HTMLInputElement;
  const pass = el("input", { class: "input", type: "password", placeholder: t("workspace_pass", lang), maxlength: "200" }) as HTMLInputElement;
  const add = el("button", { class: "pri" }, t("workspace_add", lang));
  add.onclick = async () => {
    try {
      const res = await ctx.api.workspaceCreate({
        name: name.value.trim() || "PC virtual",
        tailscale_ip: ip.value.trim(),
        username: user.value.trim(),
        password: pass.value,
      });
      pass.value = "";
      selectedId = res.vm.id;
      if (res.vm.agent_token) toast("Token do agente (uma vez): " + res.vm.agent_token);
      after();
    } catch (e) {
      toast((e as { message?: string }).message ?? "erro");
    }
  };
  const ping = el("button", {}, t("workspace_connect", lang));
  ping.onclick = async () => {
    if (!selectedId) return;
    try {
      const h = await ctx.api.workspaceHealth(selectedId);
      toast(h.status);
    } catch (e) {
      toast((e as { message?: string }).message ?? "erro");
    }
  };
  const auto = el("button", {}, t("workspace_autologon", lang));
  auto.onclick = async () => {
    if (!selectedId) return;
    if (!(await confirmDialog("Aplicar AutoAdminLogon nesta VM?", t("workspace_autologon", lang)))) return;
    try {
      await ctx.api.workspaceAutologon(selectedId);
      toast("auto-logon enviado");
    } catch (e) {
      toast((e as { message?: string }).message ?? "erro");
    }
  };
  const studio = el("button", { class: "ghost" }, "Abrir Studio");
  studio.onclick = async () => {
    if (!selectedId) return;
    try {
      await ctx.api.workspaceJob(selectedId, "open_app", { app: "studio" });
    } catch (e) {
      toast((e as { message?: string }).message ?? "erro");
    }
  };
  const dl = el("button", { class: "ghost" });
  dl.append(icon("download", 14), " agente");
  dl.onclick = async () => {
    const src = await ctx.api.getRaw("/api/workspace/agent.py");
    ctx.download("arkher_agent.py", src);
  };
  box.append(name, ip, user, pass, el("div", { class: "row" }, add, ping, auto, studio, dl));
  return box;
}

function pilotChat(ctx: Ctx, vmId: () => string | null): HTMLElement {
  const wrap = el("div", { class: "ws-chat" });
  wrap.append(el("h2", {}, "Comandos no PC"));
  wrap.append(
    el(
      "p",
      { class: "dim" },
      "abre o Studio · print · digita … · clica X Y · gera um obby e importa · lista arquivos",
    ),
  );
  const msgs = el("div", { class: "ws-msgs" });
  const paint = () => {
    msgs.textContent = "";
    for (const m of log) {
      const b = el("div", { class: `msg ${m.role}` });
      const body = el("div", { class: "msg-bubble" });
      body.innerHTML = renderMarkdown(m.content).html;
      b.append(body);
      msgs.append(b);
    }
    msgs.scrollTop = msgs.scrollHeight;
  };
  paint();
  const input = el("textarea", { class: "input", rows: "2", placeholder: "Faz X no PC…" }) as HTMLTextAreaElement;
  const send = el("button", { class: "pri" }, t("send", ctx.store.state.settings.lang));
  const go = async () => {
    const text = input.value.trim();
    const id = vmId();
    if (!text || !id) {
      toast(id ? "escreva o comando" : "selecione um PC");
      return;
    }
    input.value = "";
    log.push({ role: "user", content: text });
    paint();
    try {
      const r = await ctx.api.workspacePilot(id, text);
      log.push({ role: "assistant", content: String(r.reply ?? "") });
    } catch (e) {
      log.push({ role: "assistant", content: (e as { message?: string }).message ?? "erro" });
    }
    paint();
  };
  send.onclick = () => void go();
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void go();
    }
  });
  wrap.append(msgs, el("div", { class: "composer" }, input, send));
  return wrap;
}

export type { Vm };
