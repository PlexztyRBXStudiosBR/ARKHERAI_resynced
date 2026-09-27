// Ponte do site (Vercel HTTPS ou HTTP no PC) ate o agente.
// No celular HTTPS nao pode chamar http:// — usa :8443 com cert Tailscale.

export const PC_HOST = "arkher-windows-24.tail91d201.ts.net";

export const URL_HTTPS_PC = `https://${PC_HOST}:8443`;
export const URL_CELULAR = `http://${PC_HOST}:8710`;

let agente = "";

function add(list: string[], u: string): void {
  const x = u.replace(/\/$/, "");
  if (x && !list.includes(x)) list.push(x);
}

export function paginaHttps(): boolean {
  return typeof location !== "undefined" && location.protocol === "https:";
}

export function candidatosAgente(): string[] {
  const out: string[] = [];
  if (paginaHttps()) {
    add(out, URL_HTTPS_PC);
    add(out, `https://${PC_HOST}`);
    return out;
  }
  if (typeof location !== "undefined") {
    add(out, `http://${location.hostname}:8765`);
  }
  add(out, `http://${PC_HOST}:8765`);
  return out;
}

export async function acharAgente(): Promise<string> {
  if (agente) return agente;
  const list = candidatosAgente();
  for (const b of list) {
    try {
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(), 2500);
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
  return list[0] || "";
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

export function urlApiVercel(): string {
  return URL_HTTPS_PC;
}
