// Shell do aplicativo + controlador: liga estado, API e telas.

import { Store } from "../state/store";
import type { Screen as ScreenId } from "../state/store";
import { makeApi } from "../services/api";
import type { ApiError, Message } from "../services/api";
import { t } from "../services/i18n";
import type { StringKey } from "../services/i18n";
import { el, toast } from "../components/ui";
import { icon } from "../components/icons";
import { renderChat, afterChatRender } from "../screens/chat";
import { render3D } from "../screens/three_d";
import { renderRender } from "../screens/render";
import { renderTraining } from "../screens/training"
import { renderIntegrations } from "../screens/integrations";
import { renderCerebro } from "../screens/cerebro";
import { renderTools } from "../screens/tools";
import { renderSettings } from "../screens/settings";
import { saveToken } from "../state/store";

export interface Ctx {
  store: Store;
  api: ReturnType<typeof makeApi>;
  draft: string;
  focusComposer: boolean;
  version: string | null;
  base: () => string;
  send: (text: string, replaceLastUser?: boolean) => Promise<void>;
  cancel: () => Promise<void>;
  regenerate: () => Promise<void>;
  openSession: (id: string) => Promise<void>;
  refreshSessions: () => Promise<void>;
  exportSession: () => void;
  download: (name: string, content: string, contentB64?: string) => void;
  rate: (hash: string, rating: number, btn: HTMLButtonElement) => Promise<void>;
}

export async function boot(container: HTMLElement): Promise<void> {
  const store = new Store();
  // Em Vercel, a API persistente vem de VITE_ARKHER_API. Em desenvolvimento
  // vazio mantém o proxy/origem local configurado pelo projeto.
  const configuredApi = (import.meta.env.VITE_ARKHER_API as string | undefined) ?? "";
  const base = () => (store.state.settings.backendBase || configuredApi).replace(/\/$/, "");
  const api = makeApi(base, () => store.state.token);

  const ctx: Ctx = {
    store,
    api,
    draft: "",
    focusComposer: false,
    version: null,
    base,
    send,
    cancel,
    regenerate,
    openSession,
    refreshSessions,
    exportSession,
    download,
    rate,
  };

  applyTheme(store);
  renderShell(container, ctx);

  // identidade de dispositivo (auth própria, modo local)
  try {
    if (!store.state.token) {
      const res = await api.register(store.state.settings.userName || "usuário");
      store.set({ token: res.token });
      saveToken(res.token);
    }
    try {
      await refreshSessions();
    } catch (e) {
      // token antigo/inválido (ex.: dados do servidor recriados) → re-registra
      if ((e as ApiError).status === 401) {
        const res = await api.register(store.state.settings.userName || "usuário");
        store.set({ token: res.token });
        saveToken(res.token);
        await refreshSessions();
      } else {
        throw e;
      }
    }
  } catch {
    store.setUiFromHealth(false, undefined, null);
  }

  void pollStatus();
  setInterval(() => void pollStatus(), 5000);

  async function pollStatus(): Promise<void> {
    try {
      const h = await api.health();
      const m = await api.modelStatus();
      ctx.version = h.version ?? null;
      store.setUiFromHealth(true, m.state, null);
    } catch (e) {
      store.setUiFromHealth(false, undefined, e as ApiError);
    }
    render();
  }

  async function refreshSessions(): Promise<void> {
    const res = await api.sessions();
    store.set({ sessions: res.sessions });
  }

  async function openSession(id: string): Promise<void> {
    try {
      const res = await api.session(id);
      store.set({ currentSessionId: id, messages: res.messages, streamingContent: "" });
      render();
    } catch (e) {
      toast((e as ApiError).message);
    }
  }

  let aborter: AbortController | null = null;

  async function send(textRaw: string, replaceLastUser = false): Promise<void> {
    const text = textRaw.trim();
    if (!text || store.state.ui === "generating") return;
    ctx.draft = "";
    const input = document.getElementById("composer-input") as HTMLTextAreaElement | null;
    if (input) input.value = "";

    let messages = [...store.state.messages];
    if (replaceLastUser) {
      // espelha localmente o que o backend fará (truncate_from_last_user)
      for (let i = messages.length - 1; i >= 0; i--) {
        if (messages[i].role === "user") {
          messages = messages.slice(0, i);
          break;
        }
      }
      store.set({ messages });
    }

    store.set({ ui: "generating", messages: [...messages], streamingContent: "" });
    render();

    aborter = new AbortController();
    let session = store.state.currentSessionId;
    let collected = "";
    let erro: ApiError | null = null;
    let doneKind = "texto";
    let doneHash: string | undefined;
    let doneArquivo: { nome: string; conteudo?: string; conteudo_b64?: string } | undefined;

    try {
      for await (const ev of api.chat(text, session, store.state.settings.memoryEnabled, aborter.signal, replaceLastUser)) {
        if (ev.event === "meta") {
          session = String(ev.data["session_id"] ?? session);
          store.set({ genId: String(ev.data["gen_id"] ?? ""), currentSessionId: session });
        } else if (ev.event === "token") {
          collected += String(ev.data["t"] ?? "");
          store.set({ streamingContent: collected });
          render();
        } else if (ev.event === "done") {
          collected = String(ev.data["content"] ?? collected);
          doneKind = String(ev.data["kind"] ?? "texto");
          if (typeof ev.data["content_hash"] === "string") doneHash = ev.data["content_hash"];
          const arq = ev.data["arquivo"];
          if (arq && typeof arq === "object" && "nome" in arq) {
            doneArquivo = arq as { nome: string; conteudo?: string; conteudo_b64?: string };
          }
        } else if (ev.event === "error") {
          erro = { code: String(ev.data["code"]), message: String(ev.data["message"]), status: 0 };
        }
      }
    } catch (e) {
      const err = e as ApiError;
      if (err.code && err.code !== "NETWORK") erro = err;
      else erro = { code: "NETWORK", message: t("err_backend", store.state.settings.lang), status: 0 };
    }

    const finalMessages: Message[] = [...messages, { role: "user", content: text, kind: "texto", created_at: "" }];
    if (erro) {
      const honest =
        erro.code === "MODEL_NOT_INSTALLED"
          ? t("err_model", store.state.settings.lang)
          : erro.code === "NETWORK"
            ? t("err_backend", store.state.settings.lang)
            : `${t("err_generic", store.state.settings.lang)} ${erro.code} — ${erro.message}`;
      finalMessages.push({ role: "assistant", content: `⚠ ${honest}`, kind: "erro", created_at: "" });
      store.log(`chat erro: ${erro.code}`);
    } else if (collected) {
      finalMessages.push({
        role: "assistant",
        content: collected,
        kind: doneKind,
        created_at: "",
        hash: doneHash,
        arquivo: doneArquivo,
      });
    }
    store.set({ messages: finalMessages, streamingContent: "", ui: "ready", genId: null });
    void refreshSessions().then(render);
    render();
  }

  async function cancel(): Promise<void> {
    const gen = store.state.genId;
    aborter?.abort();
    if (gen) {
      try {
        await api.stop(gen);
      } catch {
        /* melhor esforço */
      }
    }
    if (store.state.streamingContent) {
      store.set({
        messages: [
          ...store.state.messages,
          { role: "user", content: "…", kind: "texto", created_at: "" },
          { role: "assistant", content: store.state.streamingContent + "\n\n_(geração cancelada)_", kind: "cancelada", created_at: "" },
        ],
        streamingContent: "",
        ui: "ready",
      });
    } else {
      store.set({ ui: "ready" });
    }
    render();
  }

  async function regenerate(): Promise<void> {
    const msgs = store.state.messages;
    let lastUser = "";
    for (let i = msgs.length - 1; i >= 0; i--) {
      if (msgs[i].role === "user") {
        lastUser = msgs[i].content;
        break;
      }
    }
    if (!lastUser) return;
    await send(lastUser, true);
  }

  function exportSession(): void {
    const s = store.state;
    const payload = {
      exportado_em: new Date().toISOString(),
      conversa: s.currentSessionId,
      mensagens: s.messages.map((m) => ({ papel: m.role, conteudo: m.content })),
    };
    download("arkher-conversa.json", JSON.stringify(payload, null, 2));
  }

  async function rate(hash: string, rating: number, btn: HTMLButtonElement): Promise<void> {
    try {
      await api.feedback(store.state.currentSessionId ?? "", rating, hash);
      btn.disabled = true;
      btn.textContent = "✓";
      store.log(`feedback ${rating === 1 ? "positivo" : "negativo"} registrado`);
    } catch (e) {
      toast((e as ApiError).message ?? "erro");
    }
  }

  function download(name: string, content: string, contentB64?: string): void {
    let blob: Blob;
    if (contentB64) {
      const bin = atob(contentB64);
      const bytes = new Uint8Array(bin.length);
      for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
      blob = new Blob([bytes], { type: "application/octet-stream" });
    } else {
      blob = new Blob([content], { type: "application/octet-stream" });
    }
    const url = URL.createObjectURL(blob);
    const a = el("a", { href: url, download: name });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 4000);
  }

  // ------------------------------------------------------------- shell/UI
  function renderShell(host: HTMLElement, c: Ctx): void {
    host.textContent = "";
    const header = el("header", { class: "topbar" });
    const mark = el("span", { class: "mark" });
    mark.append(icon("logo", 20));
    header.append(
      el("div", { class: "logo" }, mark, el("span", { class: "name" }, "ARKHER AI")),
      el("div", { class: "sp" }),
      statusPill(c),
    );
    const nav = el("nav", { class: "tabs", id: "tabs" });
    const screens: [ScreenId, StringKey][] = [
      ["chat", "tab_chat"],
      ["3d", "tab_3d"],
      ["render", "tab_3d"],
      ["training", "tab_cerebro"],
      ["integrations", "tab_integrations"],
      ["cerebro", "tab_cerebro"],
      ["tools", "tab_tools"],
      ["settings", "tab_settings"],
    ];
    const ICONES: Record<ScreenId, string> = {
      chat: "chat", "3d": "cube", render: "cube", training: "chip", integrations: "plug", cerebro: "chip", tools: "tools", settings: "settings",
    };
    for (const [id, key] of screens) {
      const b = el("button", { class: "tab" + (c.store.state.screen === id ? " on" : ""), "data-tab": id });
      b.append(icon(ICONES[id], 15), el("span", { class: "lab" }, t(key, c.store.state.settings.lang)));
      b.onclick = () => {
        c.store.set({ screen: id as typeof c.store.state.screen });
        render();
      };
      nav.append(b);
    }
    const main = el("main", { class: "main", id: "screen" });
    host.append(header, nav, main);
    render();
  }

  function statusPill(c: Ctx): HTMLElement {
    const s = c.store.state;
    const lang = s.settings.lang;
    const map: Record<string, [string, string]> = {
      offline: ["bad", t("status_offline", lang)],
      backend_ready_model_missing: ["warn", t("status_model_missing", lang)],
      model_loading: ["work", t("status_model_loading", lang)],
      ready: ["on", t("status_ready", lang)],
      generating: ["work", t("status_generating", lang)],
      error: ["bad", t("status_error", lang)],
    };
    const [cls, label] = map[s.ui] ?? ["bad", s.ui];
    return el("div", { class: "chip status" }, el("span", { class: "dot " + cls }), el("b", {}, label));
  }

  function render(): void {
    const s = store.state;
    applyTheme(store);
    const screenHost = document.getElementById("screen");
    const tabsHost = document.getElementById("tabs");
    if (!screenHost || !tabsHost) return;

    tabsHost.querySelectorAll(".tab").forEach((b) => {
      const id = (b as HTMLElement).dataset["tab"];
      b.classList.toggle("on", id === s.screen);
      const key = TAB_KEYS[id as keyof typeof TAB_KEYS];
      const lab = (b as HTMLElement).querySelector(".lab");
      if (lab) lab.textContent = t(key, s.settings.lang);
    });
    const pillHost = document.querySelector(".topbar .chip.status");
    if (pillHost) {
      const novo = statusPill(ctx);
      pillHost.replaceWith(novo);
    }

    screenHost.textContent = "";
    if (s.screen === "chat") {
      screenHost.append(renderChat(ctx));
      afterChatRender(ctx);
    } else if (s.screen === "3d") screenHost.append(render3D(ctx));
    else if (s.screen === "render") screenHost.append(renderRender(ctx));
    else if (s.screen === "training") screenHost.append(renderTraining(ctx));
    else if (s.screen === "integrations") screenHost.append(renderIntegrations(ctx));
    else if (s.screen === "cerebro") screenHost.append(renderCerebro(ctx));
    else if (s.screen === "tools") screenHost.append(renderTools(ctx));
    else if (s.screen === "settings") screenHost.append(renderSettings(ctx));
  }
}

const TAB_KEYS = {
  chat: "tab_chat",
  "3d": "tab_3d",
  render: "tab_3d",
  training: "tab_cerebro",
  integrations: "tab_integrations",
  cerebro: "tab_cerebro",
  tools: "tab_tools",
  settings: "tab_settings",
} as const;

function applyTheme(store: Store): void {
  const { theme, fontScale } = store.state.settings;
  document.documentElement.dataset["theme"] = theme;
  document.documentElement.style.fontSize = `${16 * fontScale}px`;
}
