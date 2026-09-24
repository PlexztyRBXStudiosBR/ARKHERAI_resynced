// Cliente da API própria do ARKHER.
// Regra dura: o navegador fala SOMENTE com o backend oficial (caminhos /api).

export interface HealthInfo {
  ok: boolean;
  backend?: string;
  model_state?: string;
  version?: string;
}

export interface ModelStatus {
  ok?: boolean;
  state: string;
  checkpoint_present?: boolean;
  checkpoint_version?: string;
  parameters?: number;
  device?: string;
  quality?: string;
  error?: string;
}

export interface ApiError {
  code: string;
  message: string;
  status: number;
}

export function makeApi(baseUrl: () => string, token: () => string | null) {
    async function http<T>(method: string, path: string, body?: unknown, timeoutMs = 12000): Promise<T> {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeoutMs);
    try {
      const headers: Record<string, string> = {};
      const tk = token();
      if (tk) {
        headers["Authorization"] = `Bearer ${tk}`;
        headers["X-Arkher-Token"] = tk; // fallback para proxies que descartam Authorization
      }
      if (body !== undefined) headers["Content-Type"] = "application/json";
      const res = await fetch(`${baseUrl()}${path}`, {
        method,
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
        signal: ctrl.signal,
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detail = (data as { detail?: { code?: string; message?: string } }).detail;
        throw {
          code: detail?.code ?? `HTTP_${res.status}`,
          message: detail?.message ?? `HTTP ${res.status}`,
          status: res.status,
        } as ApiError;
      }
      return data as T;
    } catch (e) {
      if ((e as ApiError).code) throw e;
      throw { code: "NETWORK", message: "sem conexão", status: 0 } as ApiError;
    } finally {
      clearTimeout(timer);
    }
  }

  return {
    health: () => http<HealthInfo>("GET", "/api/health", undefined, 6000),
    modelStatus: () => http<ModelStatus>("GET", "/api/model/status", undefined, 6000),
    register: (name: string) => http<{ token: string }>("POST", "/api/auth/device", { name }),
    sessions: () => http<{ sessions: Session[] }>("GET", "/api/sessions"),
    createSession: () => http<{ session: Session }>("POST", "/api/sessions"),
    session: (id: string) => http<{ session: Session; messages: Message[] }>("GET", `/api/sessions/${id}`),
    renameSession: (id: string, title: string) => http<{ ok: boolean }>("PATCH", `/api/sessions/${id}`, { title }),
    deleteSession: (id: string) => http<{ ok: boolean }>("DELETE", `/api/sessions/${id}`),
    stop: (genId: string) => http<{ ok: boolean }>("POST", "/api/chat/stop", { gen_id: genId }),
    memories: (q = "") => http<{ memories: Memory[] }>("GET", `/api/memory?q=${encodeURIComponent(q)}`),
    addMemory: (text: string, project: string, consent: boolean) =>
      http<{ memory: Memory }>("POST", "/api/memory", { text, project, consent }),
    deleteMemory: (id: string) => http<{ ok: boolean }>("DELETE", `/api/memory/${id}`),
    clearMemories: () => http<{ deleted: number }>("DELETE", "/api/memory"),
    tools: () => http<{ tools: Tool[] }>("GET", "/api/tools"),
    authorizeTool: (id: string) => http<{ ok: boolean }>("POST", `/api/tools/${id}/authorize`),
    revokeTool: (id: string) => http<{ ok: boolean }>("POST", `/api/tools/${id}/revoke`),
    toolHistory: () => http<{ history: ToolLogEntry[] }>("GET", "/api/tools/history"),
    runTool: (id: string, args: Record<string, unknown>) =>
      http<{ result: unknown }>("POST", `/api/tools/${id}/run`, args),
    feedback: (sessionId: string, rating: number, contentHash: string) =>
      http<{ ok: boolean }>("POST", "/api/feedback", { session_id: sessionId, rating, content_hash: contentHash }),
    trainingStatus: () => http<TrainingStatus>("GET", "/api/training/status", undefined, 8000),
    trainingStart: (step: string) => http<TrainingStatus>("POST", "/api/training/start", { step }),
    trainingNews: () => http<{ ok: boolean; news: TrainingNewsItem[] }>("GET", "/api/training/news", undefined, 8000),
    diagnostics: () => http<Record<string, unknown>>("GET", "/api/diagnostics"),
    produtoStatus: () => http<ProdutoStatus>("GET", "/api/produto/status", undefined, 8000),
    async getRaw(path: string): Promise<string> {
      const headers: Record<string, string> = {};
      const tk = token();
      if (tk) {
        headers["Authorization"] = `Bearer ${tk}`;
        headers["X-Arkher-Token"] = tk;
      }
      const res = await fetch(`${baseUrl()}${path}`, { headers });
      if (!res.ok) throw { code: `HTTP_${res.status}`, message: `HTTP ${res.status}`, status: res.status } as ApiError;
      return res.text();
    },

    // Chat com streaming SSE real vindo do backend próprio.
    async *chat(
      message: string,
      sessionId: string | null,
      memoryEnabled: boolean,
      signal: AbortSignal,
      replaceLastUser = false,
    ) {
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      const tk = token();
      if (tk) {
        headers["Authorization"] = `Bearer ${tk}`;
        headers["X-Arkher-Token"] = tk;
      }
      const res = await fetch(`${baseUrl()}/api/chat`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          message,
          session_id: sessionId,
          memory_enabled: memoryEnabled,
          replace_last_user: replaceLastUser,
        }),
        signal,
      });
      if (!res.ok || !res.body) {
        let detail: { code?: string; message?: string } = {};
        try {
          detail = ((await res.json()) as { detail?: typeof detail }).detail ?? {};
        } catch {
          /* corpo vazio */
        }
        throw { code: detail.code ?? `HTTP_${res.status}`, message: detail.message ?? `HTTP ${res.status}`, status: res.status } as ApiError;
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        let idx = buf.indexOf("\n\n");
        while (idx >= 0) {
          const raw = buf.slice(0, idx);
          buf = buf.slice(idx + 2);
          let event = "message";
          let data = "";
          for (const line of raw.split("\n")) {
            if (line.startsWith("event:")) event = line.slice(6).trim();
            else if (line.startsWith("data:")) data = line.slice(5).trim();
          }
          if (data) yield { event, data: JSON.parse(data) as Record<string, unknown> };
          idx = buf.indexOf("\n\n");
        }
      }
    },
  };
}

export interface Session {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface Message {
  role: "user" | "assistant";
  content: string;
  kind: string;
  created_at: string;
  hash?: string;
  arquivo?: { nome: string; conteudo?: string; conteudo_b64?: string };
}

export interface Memory {
  id: string;
  text: string;
  project: string;
  created_at: string;
}

export interface Tool {
  id: string;
  nome: string;
  descricao: string;
  permissoes: string[];
  confirmacao: boolean;
  authorized: boolean;
}

export interface ToolLogEntry {
  tool_id: string;
  ok: number;
  arg_summary: string;
  ms: number;
  created_at: string;
}

export interface ProdutoStatusItem {
  id: string;
  nome: string;
  ok: boolean;
  detalhe: string;
}

export interface ProdutoStatus {
  prontos: number;
  total: number;
  itens: ProdutoStatusItem[];
  fora_do_produto_por_decisao: string[];
}

export interface TrainingNewsItem {
  quando: string;
  tipo: "checkpoint" | "relatorio" | string;
  titulo: string;
  detalhe: string;
}

export interface TrainingStatus {
  job: { step: string; running: boolean; exit_code?: number } | null;
  state: {
    status: string;
    epoch?: number;
    epochs_alvo?: number;
    passo?: number;
    perda_media?: number;
    perda?: number[];
    checkpoint?: string;
    versao?: string;
    perda_final_validacao?: number;
  };
}
