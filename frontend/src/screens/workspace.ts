// Cockpit DsOS: tela real da VM + toque + HUD + chat de piloto.
// Sem desktop HTML falso. Sem IA de terceiro no loop de visão.

import { el, toast } from "../components/ui";
import { t } from "../services/i18n";
import { renderMarkdown } from "../app/md";
import { acharAgente, mandarInput, PC_HOST } from "../services/ponte";
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
  const placeholder = el("p", { class: "dim ws-ph" }, "Tela do PC (agente :8765). Toque curto = clique.");
  const hud = makeHud();
  screen.append(placeholder, hud);
  desk.append(bar, screen);

  const setup = el("div", { class: "ws-setup" });
  setup.append(formAdd(ctx, () => {
    void refreshVms();
    startLive(img, screen, placeholder, titleEl);
  }));
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
    startLive(img, screen, placeholder, titleEl);
  };

  driveBtn.onclick = () => {
    drive = !drive;
    driveBtn.textContent = drive ? "HUD ligado" : "HUD";
    driveBtn.classList.toggle("pri", drive);
    hud.classList.toggle("on", drive);
    toast(drive ? "você dirige — toque e HUD. A IA não clica." : "HUD off — piloto no chat ao lado");
  };

  bindTouch(img);

  addBtn.onclick = () => setup.classList.toggle("on");

  side.append(pilotChat(ctx, () => selectedId));
  void refreshVms();
  startLive(img, screen, placeholder, titleEl);
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

function bindTouch(img: HTMLImageElement): void {
  let t0 = 0;
  let sx = 0;
  let sy = 0;
  let px = 0;
  let py = 0;
  let dragging = false;

  const send = (acts: Record<string, unknown>[]) => {
    mandarInput(acts);
  };

  img.addEventListener("pointerdown", (ev) => {
    if (!img.src) return;
    const p = imgToReal(img, ev.clientX, ev.clientY);
    if (!p) return;
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
    if (dragging) {
      void send([{ do: "drag", x: sx, y: sy, x2: px, y2: py }]);
    } else if (dt > 520) {
      void send([{ do: "right", x: sx, y: sy }]);
    } else if (dt < 400) {
      void send([{ do: "click", x: sx, y: sy }]);
    }
    ev.preventDefault();
  });
  img.addEventListener("pointercancel", () => {
    t0 = 0;
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
  img: HTMLImageElement,
  screen: HTMLElement,
  ph: HTMLElement,
  titleEl: HTMLElement,
): void {
  const my = ++liveGen;
  let busy = false;
  const tick = async () => {
    if (my !== liveGen) return;
    if (busy) {
      if (my === liveGen) setTimeout(tick, 200);
      return;
    }
    busy = true;
    try {
      const base = await acharAgente();
      const r = await fetch(`${base}/frame?scale=0.4&q=42`);
      if (!r.ok) throw new Error("sem frame");
      const blob = await r.blob();
      const rw = Number(r.headers.get("X-Arkher-Real-W") || 0);
      const rh = Number(r.headers.get("X-Arkher-Real-H") || 0);
      const tit = r.headers.get("X-Arkher-Title") || "";
      if (rw) geo.realW = rw;
      if (rh) geo.realH = rh;
      if (tit) titleEl.textContent = tit;
      if (blob && blob.size > 80) {
        if (lastUrl) URL.revokeObjectURL(lastUrl);
        lastUrl = URL.createObjectURL(blob);
        img.src = lastUrl;
        if (!img.isConnected) screen.append(img);
        ph.remove();
      }
    } catch (e) {
      ph.textContent = (e as { message?: string }).message ?? "agente offline";
      if (!ph.isConnected) screen.append(ph);
    }
    busy = false;
    if (my === liveGen) setTimeout(tick, 700);
  };
  void tick();
}

const HUD_KEYS: Record<string, [string, string][]> = {
  godot: [
    ["F5", "{F5}"], ["F6", "{F6}"], ["Q", "q"], ["W", "w"], ["E", "e"], ["R", "r"],
    ["F", "f"], ["^S", "^s"], ["^Z", "^z"], ["^D", "^d"], ["Del", "{DEL}"],
  ],
  studio: [
    ["F5", "{F5}"], ["F8", "{F8}"], ["1", "1"], ["2", "2"], ["3", "3"], ["4", "4"],
    ["R", "r"], ["T", "t"], ["F", "{F}"], ["^S", "^s"], ["^G", "^g"],
  ],
  blender: [
    ["G", "g"], ["R", "r"], ["S", "s"], ["E", "e"], ["Tab", "{TAB}"], ["Z", "z"],
    ["X", "x"], ["^S", "^s"], ["+A", "+a"], ["7", "{NUMPAD7}"], ["1", "{NUMPAD1}"],
  ],
  geral: [
    ["Esc", "{ESC}"], ["Enter", "{ENTER}"], ["Espaço", " "], ["Tab", "{TAB}"],
    ["^Z", "^z"], ["^S", "^s"], ["^C", "^c"], ["^V", "^v"], ["Del", "{DEL}"],
  ],
};

function makeHud(): HTMLElement {
  const hud = el("div", { class: "ws-hud" });
  const send = (acts: Record<string, unknown>[]) => {
    mandarInput(acts);
  };
  const key = (label: string, k: string) => {
    const b = el("button", { type: "button", class: "ws-hk" }, label);
    b.onclick = () => send([{ do: "key", key: k }]);
    return b;
  };
  const stick = el("div", { class: "ws-stick" });
  const knob = el("div", { class: "ws-stick-knob" });
  stick.append(knob);
  let hold: ReturnType<typeof setTimeout> | null = null;
  let ax = 0, ay = 0, down = false;
  const pulse = () => {
    if (!down) return;
    send([{ do: "stick", x: ax, y: ay }]);
    hold = setTimeout(pulse, 70);
  };
  const setKnob = (nx: number, ny: number) => {
    ax = Math.max(-1, Math.min(1, nx));
    ay = Math.max(-1, Math.min(1, ny));
    knob.style.transform = `translate(${ax * 22}px, ${ay * 22}px)`;
  };
  const fromEv = (ev: PointerEvent) => {
    const r = stick.getBoundingClientRect();
    const nx = (ev.clientX - (r.left + r.width / 2)) / (r.width / 2);
    const ny = (ev.clientY - (r.top + r.height / 2)) / (r.height / 2);
    setKnob(nx, ny);
  };
  stick.addEventListener("pointerdown", (ev) => {
    down = true;
    stick.setPointerCapture(ev.pointerId);
    fromEv(ev);
    if (hold) clearTimeout(hold);
    pulse();
  });
  stick.addEventListener("pointermove", (ev) => {
    if (down) fromEv(ev);
  });
  const end = () => {
    down = false;
    setKnob(0, 0);
    if (hold) clearTimeout(hold);
    hold = null;
  };
  stick.addEventListener("pointerup", end);
  stick.addEventListener("pointercancel", end);

  const modes = el("div", { class: "ws-hud-row" });
  const keysBox = el("div", { class: "ws-hud-row" });
  let modo = "godot";
  const paintKeys = () => {
    keysBox.textContent = "";
    for (const [lab, k] of HUD_KEYS[modo] || HUD_KEYS.geral) keysBox.append(key(lab, k));
  };
  for (const m of ["godot", "studio", "blender", "geral"] as const) {
    const b = el("button", { type: "button", class: "ws-hk" }, m);
    b.onclick = () => {
      modo = m;
      paintKeys();
    };
    modes.append(b);
  }
  paintKeys();
  const apps = el("div", { class: "ws-hud-row" });
  const mkApp = (lab: string, nome: string) => {
    const b = el("button", { class: "ws-hk" }, lab);
    b.onclick = () => send([{ do: "app", nome }]);
    return b;
  };
  const mix = el("button", { class: "ws-hk" }, "Mixamo");
  mix.onclick = () => send([{ do: "url", url: "https://www.mixamo.com" }]);
  const ph = el("button", { class: "ws-hk" }, "Poly Haven");
  ph.onclick = () => send([{ do: "url", url: "https://polyhaven.com/models" }]);
  apps.append(mkApp("Godot", "godot"), mkApp("Studio", "studio"), mkApp("Blender", "blender"), mix, ph);
  const kb = el("input", { class: "input ws-hud-kb", placeholder: "digita na VM…", maxlength: "200" }) as HTMLInputElement;
  kb.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      const t = kb.value;
      if (t) send([{ do: "type", text: t }]);
      kb.value = "";
    }
  });
  hud.append(
    el("p", { class: "dim" }, "HUD analógico + teclas do software. Toque na tela = clique."),
    stick,
    modes,
    keysBox,
    apps,
    kb,
  );
  return hud;
}

function formAdd(ctx: Ctx, after: () => void): HTMLElement {
  const lang = ctx.store.state.settings.lang;
  const box = el("div", { class: "memory-form" });
  box.append(el("p", { class: "dim" }, t("workspace_hint", lang) + " Usuário: nexus (automático)."));
  const ip = el("input", { class: "input", placeholder: t("workspace_ip", lang), maxlength: "80" }) as HTMLInputElement;
  ip.value = PC_HOST;
  const pass = el("input", { class: "input", type: "password", placeholder: t("workspace_pass", lang), maxlength: "200" }) as HTMLInputElement;
  const add = el("button", { class: "pri" }, t("workspace_add", lang));
  add.onclick = async () => {
    try {
      const res = await ctx.api.workspaceLigar(ip.value.trim() || PC_HOST, pass.value);
      pass.value = "";
      selectedId = res.vm.id;
      toast("ligado como " + (res.user || "nexus"));
      after();
    } catch (e) {
      toast((e as { message?: string }).message ?? "erro");
    }
  };
  box.append(ip, pass, el("div", { class: "row" }, add));
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
