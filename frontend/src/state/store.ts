// Estado global simples e observável. Persistência local apenas de preferências.

import type { ApiError, Message, Session } from "../services/api";
import type { Lang } from "../services/i18n";

export type UiState =
  | "offline"
  | "backend_ready_model_missing"
  | "model_loading"
  | "ready"
  | "generating"
  | "error";

export type Screen = "chat" | "memory" | "tools" | "training" | "settings";

export interface Settings {
  userName: string;
  lang: Lang;
  theme: "dark" | "light";
  fontScale: number; // 0.85 | 1 | 1.15
  memoryEnabled: boolean;
  safeMode: boolean;
  backendBase: string; // "" = mesmo servidor
}

export interface StoreState {
  settings: Settings;
  token: string | null;
  ui: UiState;
  lastError: string | null;
  screen: Screen;
  sessions: Session[];
  currentSessionId: string | null;
  messages: Message[];
  streamingContent: string;
  genId: string | null;
  localLogs: string[];
}

const SETTINGS_KEY = "arkher_settings_v1";
const TOKEN_KEY = "arkher_token_v1";

export const DEFAULT_SETTINGS: Settings = {
  userName: "",
  lang: "pt-BR",
  theme: "dark",
  fontScale: 1,
  memoryEnabled: true,
  safeMode: true,
  backendBase: "",
};

export function loadSettings(): Settings {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (raw) return { ...DEFAULT_SETTINGS, ...(JSON.parse(raw) as Partial<Settings>) };
  } catch {
    /* prefereências corrompidas: usa padrão */
  }
  return { ...DEFAULT_SETTINGS };
}

export function saveSettings(s: Settings): void {
  localStorage.setItem(SETTINGS_KEY, JSON.stringify(s));
}

export function loadToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function saveToken(t: string | null): void {
  if (t) localStorage.setItem(TOKEN_KEY, t);
  else localStorage.removeItem(TOKEN_KEY);
}

export type Listener = () => void;

export class Store {
  state: StoreState;
  private listeners = new Set<Listener>();

  constructor() {
    this.state = {
      settings: loadSettings(),
      token: loadToken(),
      ui: "offline",
      lastError: null,
      screen: "chat",
      sessions: [],
      currentSessionId: null,
      messages: [],
      streamingContent: "",
      genId: null,
      localLogs: [],
    };
  }

  subscribe(fn: Listener): () => void {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  set(patch: Partial<StoreState>): void {
    this.state = { ...this.state, ...patch };
    for (const l of this.listeners) l();
  }

  updateSettings(patch: Partial<Settings>): void {
    const settings = { ...this.state.settings, ...patch };
    saveSettings(settings);
    this.set({ settings });
  }

  log(line: string): void {
    const stamp = new Date().toISOString().slice(11, 19);
    const logs = [...this.state.localLogs.slice(-199), `${stamp} ${line}`];
    this.state = { ...this.state, localLogs: logs };
  }

  setUiFromHealth(backendOk: boolean, modelState: string | undefined, err: ApiError | null): void {
    let ui: UiState;
    if (!backendOk) ui = "offline";
    else if (modelState === "ready") ui = this.state.ui === "generating" ? "generating" : "ready";
    else if (modelState === "model_loading" || modelState === "loading") ui = "model_loading";
    else if (modelState === "error") ui = "error";
    else ui = "backend_ready_model_missing";
    this.set({ ui, lastError: err ? err.message : null });
  }
}
