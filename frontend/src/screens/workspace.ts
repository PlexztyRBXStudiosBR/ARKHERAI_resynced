// Cockpit DsOS: tela real da VM + toque + HUD + chat de piloto.
// Sem desktop HTML falso. Sem IA de terceiro no loop de visão.

import { confirmDialog, el, toast } from "../components/ui";
import { icon } from "../components/icons";
import { t } from "../services/i18n";
import { renderMarkdown } from "../app/md";
import type { Vm } from "../services/api";
import type { Ctx } from "../app/app";

let liveGen = 0;
let selectedId: string | null = null;
let drive = false; // HUD: eu dirijo (Studio/Blender) sem a IA
let lastUrl = "";
const geo = { realW: 1920, realH: 1080, imgW: 0, imgH: 0 };
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
  const driveBtn = el("button", { class: "ghost" }, "HUD");
  const addBtn = el("button", { class: "ghost" }, t("workspace_add", lang));
  const titleEl = el("span", { class: "ws-win dim" }, "");
  bar.append(sel, liveBtn, driveBtn, addBtn, titleEl);

  const screen = el("div", { class: "ws-screen" });
  const img = el("img", { alt: "tela da VM", class: "ws-frame" }) as HTMLImageElement;
  img.draggable = false;
  const placeholder = el("p", { class: "dim ws-ph" }, "Windows App → cadastre o IP 100.x → Tela ao vivo. Toque na tela. HUD pra dirigir o Studio/Blender sem a IA.");
  const hud = makeHud(ctx, () => selectedId);
  screen.append(placeholder, hud);
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
    startLive(ctx, selectedId, img, screen, placeholder, titleEl);
  };

  driveBtn.onclick = () => {
    drive = !drive;
    driveBtn.textContent = drive ? "HUD ligado" : "HUD";
    driveBtn.classList.toggle("pri", drive);
    hud.classList.toggle("on", drive);
    toast(drive ? "você dirige — toque e HUD. A IA não clica." : "HUD off — piloto no chat ao lado");
  };

  bindTouch(ctx, img, () => selectedId);

  addBtn.onclick = () => setup.classList.toggle("on");

  side.append(pilotChat(ctx, () => selectedId));
  void refreshVms();
  return root;
}

function imgToReal(img: HTMLImageElement, clientX: number, clientY: number): { x: number; y: number } | null {
  const r = img.getBoundingClientRect();
  if (!r.width || !r.height) return null;
  const nx = (clientX - r.left) / r.width;
  const ny = (clientY - r.top) / r.height;
  if (nx < 0 || ny < 0 || nx > 1 || ny > 1) return null;
  const rw = geo.realW || img.naturalWidth || 1920;
  const rh = geo.realH || img.naturalHeight || 1080;
  return { x: Math.round(nx * rw), y: Math.round(ny * rh) };
}

function bindTouch(ctx: Ctx, img: HTMLImageElement, vmId: () => string | null): void {
  let t0 = 0;
  let sx = 0;
  let sy = 0;
  let px = 0;
  let py = 0;
  let dragging = false;
  let fingers = 0;

  const send = async (acts: Record<string, unknown>[]) => {
    const id = vmId();
    if (!id || !acts.length) return;
    try {
      await ctx.api.workspaceInput(id, acts);
    } catch (e) {
      toast((e as { message?: string }).message ?? "toque falhou");
    }
  };

  img.addEventListener("pointerdown", (ev) => {
    if (!img.src) return;
    const p = imgToReal(img, ev.clientX, ev.clientY);
    if (!p) return;
    fingers += 1;
    t0 = Date.now();
    sx = p.x;
    sy = p.y;
    px = p.x;
    py = p.y;
    dragging = false;
    img.setPointerCapture(ev.pointerId);
    ev.preventDefault();
  });
  img.addEventListener("pointermove", (ev) => {
    if (!t0) return;
    const p = imgToReal(img, ev.clientX, ev.clientY);
    if (!p) return;
    if (Math.hypot(p.x - sx, p.y - sy) > 12) dragging = true;
    px = p.x;
    py = p.y;
  });
  img.addEventListener("pointerup", (ev) => {
    if (!t0) return;
    const dt = Date.now() - t0;
    t0 = 0;
    fingers = Math.max(0, fingers - 1);
    if (dragging) {
      void send([{ do: "drag", x: sx, y: sy, x2: px, y2: py }]);
    } else if (dt > 520) {
      void send([{ do: "right", x: sx, y: sy }]);
    } else if (dt < 280) {
      void send([{ do: "click", x: sx, y: sy }]);
    }
    ev.preventDefault();
  });
  img.addEventListener("pointercancel", () => {
    t0 = 0;
    fingers = 0;
  });
  img.addEventListener("wheel", (ev) => {
    const p = imgToReal(img, ev.clientX, ev.clientY);
    if (!p) return;
    ev.preventDefault();
    const amount = ev.deltaY > 0 ? -240 : 240;
    void send([{ do: "scroll", x: p.x, y: p.y, amount }]);
  }, { passive: false });
  img.addEventListener("dblclick", (ev) => {
    const p = imgToReal(img, ev.clientX, ev.clientY);
    if (!p) return;
    void send([{ do: "dblclick", x: p.x, y: p.y }]);
  });
}

function startLive(
  ctx: Ctx,
  vmId: string,
  img: HTMLImageElement,
  screen: HTMLElement,
  ph: HTMLElement,
  titleEl: HTMLElement,
): void {
  const my = ++liveGen;
  let busy = false;
  void (async () => {
    try {
      const g = await ctx.api.workspaceGuiReady(vmId);
      if (!g.ok) ph.textContent = g.nota || g.err || "sem sessão gráfica (Windows App desbloqueado + agente nesta sessão)";
    } catch {
      /* health do print basta */
    }
  })();
  const tick = async () => {
    if (my !== liveGen) return;
    if (busy) {
      if (my === liveGen) setTimeout(tick, 900);
      return;
    }
    busy = true;
    try {
      let blob: Blob | null = null;
      try {
        const f = await ctx.api.workspaceFrame(vmId, 0.45, 48);
        blob = f.blob;
        if (f.realW) geo.realW = f.realW;
        if (f.realH) geo.realH = f.realH;
        if (f.titulo) titleEl.textContent = f.titulo;
      } catch {
        const s = await ctx.api.workspaceScreen(vmId, 0.45, 48);
        const b64 = s.b64 || (s.img && s.img.includes(",") ? s.img.split(",")[1] : "") || "";
        if (b64) {
          const bin = atob(b64);
          const arr = new Uint8Array(bin.length);
          for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
          blob = new Blob([arr], { type: "image/jpeg" });
        }
        if (s.real_w) geo.realW = Number(s.real_w);
        if (s.real_h) geo.realH = Number(s.real_h);
        if (s.titulo) titleEl.textContent = s.titulo;
        if (!b64) ph.textContent = s.message ?? "sem frame";
      }
      if (blob && blob.size > 80) {
        if (lastUrl) URL.revokeObjectURL(lastUrl);
        lastUrl = URL.createObjectURL(blob);
        img.src = lastUrl;
        if (!img.isConnected) screen.append(img);
        ph.remove();
      } else if (!ph.isConnected) {
        screen.append(ph);
      }
    } catch (e) {
      ph.textContent = (e as { message?: string }).message ?? "agente offline";
      if (!ph.isConnected) screen.append(ph);
    }
    busy = false;
    if (my === liveGen) setTimeout(tick, 2200);
  };
  void tick();
}

function makeHud(ctx: Ctx, vmId: () => string | null): HTMLElement {
  const hud = el("div", { class: "ws-hud" });
  const send = (acts: Record<string, unknown>[]) => {
    const id = vmId();
    if (!id) return;
    void ctx.api.workspaceInput(id, acts).catch((e) => toast((e as { message?: string }).message ?? "hud"));
  };
  const key = (label: string, k: string) => {
    const b = el("button", { type: "button", class: "ws-hk" }, label);
    b.onclick = () => send([{ do: "key", key: k }]);
    return b;
  };
  const pad = el("div", { class: "ws-pad" });
  pad.append(
    el("span", {}),
    key("▲", "{UP}"),
    el("span", {}),
    key("◀", "{LEFT}"),
    key("OK", "{ENTER}"),
    key("▶", "{RIGHT}"),
    el("span", {}),
    key("▼", "{DOWN}"),
    el("span", {}),
  );
  const row = el("div", { class: "ws-hud-row" });
  row.append(
    key("ESC", "{ESC}"),
    key("TAB", "{TAB}"),
    key("⌫", "{BACKSPACE}"),
    key("Espaço", " "),
  );
  const apps = el("div", { class: "ws-hud-row" });
  const studio = el("button", { class: "ws-hk" }, "Studio");
  studio.onclick = () => send([{ do: "app", nome: "studio" }]);
  const blender = el("button", { class: "ws-hk" }, "Blender");
  blender.onclick = () => send([{ do: "app", nome: "blender" }]);
  apps.append(studio, blender);
  const kb = el("input", { class: "input ws-hud-kb", placeholder: "digita na VM…", maxlength: "200" }) as HTMLInputElement;
  kb.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      const t = kb.value;
      if (t) send([{ do: "type", text: t }]);
      kb.value = "";
    }
  });
  hud.append(el("p", { class: "dim" }, "HUD — você dirige. Toque curto = clique, longo = direito, arrasta = drag."), pad, row, apps, kb);
  return hud;
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
  const dl = el("button", { class: "ghost" });
  dl.append(icon("download", 14), " agente");
  dl.onclick = async () => {
    const src = await ctx.api.getRaw("/api/workspace/agent.py");
    ctx.download("arkher_agent.py", src);
  };
  box.append(name, ip, user, pass, el("div", { class: "row" }, add, ping, auto, dl));
  return box;
}

function pilotChat(ctx: Ctx, vmId: () => string | null): HTMLElement {
  const wrap = el("div", { class: "ws-chat" });
  wrap.append(el("h2", {}, "Comandos no PC"));
  wrap.append(
    el(
      "p",
      { class: "dim" },
      drive
        ? "HUD ligado: você dirige. Desligue o HUD pra a ARKHER operar."
        : "abre o Studio · print · digita … · clica X Y · gera um obby e importa",
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
    if (drive) {
      toast("HUD ligado — desligue pra a ARKHER clicar por você");
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
