import { describe, expect, it, vi } from "vitest";
import { makeApi } from "../src/services/api";

describe("cliente da API própria", () => {
  it("usa apenas caminhos /api (nenhum provedor externo)", async () => {
    const calls: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        calls.push(url);
        return new Response(JSON.stringify({ ok: true, backend: "ready", model_state: "ready", version: "0.1.0" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }),
    );
    const api = makeApi(() => "", () => "ark_token");
    await api.health();
    expect(calls).toEqual(["/api/health"]);
    for (const c of calls) expect(c.startsWith("/api/")).toBe(true);
  });

  it(
    "timeout vira erro honesto (nunca carregamento infinito)",
    async () => {
      vi.stubGlobal(
        "fetch",
        vi.fn(
          (_url: string, init: { signal: AbortSignal }) =>
            new Promise((_resolve, reject) => {
              init.signal.addEventListener("abort", () => reject(new Error("abort")));
            }),
        ),
      );
      const api = makeApi(() => "", () => null);
      await expect(api.health()).rejects.toMatchObject({ code: "NETWORK" });
    },
    10000,
  );

  it("erro HTTP propaga código e mensagem do backend", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        new Response(
          JSON.stringify({ detail: { code: "MODEL_NOT_INSTALLED", message: "modelo ausente" } }),
          { status: 409, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    const api = makeApi(() => "", () => "t");
    await expect(api.modelStatus()).rejects.toMatchObject({ code: "MODEL_NOT_INSTALLED" });
  });
});
