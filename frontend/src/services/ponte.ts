// Agente direto (porta 8765), igual o ArkherAI antigo. Sem URL de backend.

export const PC_HOST = "arkher-windows-24.tail91d201.ts.net";

let agente = "";

function add(list: string[], u: string): void {
  const x = u.replace(/\/$/, "");
  if (x && !list.includes(x)) list.push(x);
}

export function candidatosAgente(): string[] {
  const out: string[] = [];
  if (typeof location !== "undefined") {
    add(out, `http://${location.hostname}:8765`);
    add(out, `${location.protocol}//${location.hostname}:8765`);
  }
  add(out, `http://${PC_HOST}:8765`);
  return out;
}

export async function acharAgente(): Promise<string> {
  if (agente) return agente;
  for (const b of candidatosAgente()) {
    try {
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(), 2000);
      const r = await fetch(`${b}/health`, { signal: ctrl.signal });
      clearTimeout(t);
      if (r.ok) {
        agente = b;
        return b;
      }
    } catch {
      /* próximo */
    }
  }
  return candidatosAgente()[0] || "";
}

export function mandarInput(acts: Record<string, unknown>[]): void {
  const b = agente || candidatosAgente()[0];
  if (!b || !acts.length) return;
  void fetch(`${b}/input`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ acts }),
    keepalive: true,
  }).catch(() => {
    /* clique não espera */
  });
}

export const URL_CELULAR = `http://${PC_HOST}:8710`;
