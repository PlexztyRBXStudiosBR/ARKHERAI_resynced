import { beforeEach, describe, expect, it, vi } from "vitest";
import { DEFAULT_SETTINGS, Store } from "../src/state/store";

// localStorage mínimo para ambiente de teste
const mem = new Map<string, string>();
vi.stubGlobal("localStorage", {
  getItem: (k: string) => mem.get(k) ?? null,
  setItem: (k: string, v: string) => void mem.set(k, v),
  removeItem: (k: string) => void mem.delete(k),
});

describe("máquina de estados da interface", () => {
  let store: Store;
  beforeEach(() => {
    mem.clear();
    store = new Store();
  });

  it("começa offline até o health responder", () => {
    expect(store.state.ui).toBe("offline");
  });

  it("backend ok sem modelo → backend_ready_model_missing", () => {
    store.setUiFromHealth(true, "model_not_installed", null);
    expect(store.state.ui).toBe("backend_ready_model_missing");
  });

  it("modelo carregando → model_loading", () => {
    store.setUiFromHealth(true, "model_loading", null);
    expect(store.state.ui).toBe("model_loading");
  });

  it("modelo pronto → ready", () => {
    store.setUiFromHealth(true, "ready", null);
    expect(store.state.ui).toBe("ready");
  });

  it("backend fora → offline com erro registrado", () => {
    store.setUiFromHealth(false, undefined, { code: "NETWORK", message: "x", status: 0 });
    expect(store.state.ui).toBe("offline");
    expect(store.state.lastError).toBe("x");
  });

  it("gerando preserva estado durante health ready", () => {
    store.set({ ui: "generating" });
    store.setUiFromHealth(true, "ready", null);
    expect(store.state.ui).toBe("generating");
  });

  it("preferências persistem", () => {
    store.updateSettings({ theme: "light", fontScale: 1.15 });
    const outra = new Store();
    expect(outra.state.settings.theme).toBe("light");
    expect(outra.state.settings.fontScale).toBe(1.15);
    expect(DEFAULT_SETTINGS.theme).toBe("dark");
  });
});
