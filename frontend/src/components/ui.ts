// Componentes utilitários: criação de elementos, modal de confirmação, toasts.

export function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  attrs: Record<string, string> = {},
  ...children: (Node | string)[]
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k.startsWith("data-")) node.setAttribute(k, v);
    else node.setAttribute(k, v);
  }
  for (const c of children) node.append(c);
  return node;
}

export function confirmDialog(message: string, confirmLabel = "Confirmar"): Promise<boolean> {
  return new Promise((resolve) => {
    const overlay = el("div", { class: "overlay" });
    const box = el("div", { class: "modal", role: "dialog", "aria-modal": "true" });
    const txt = el("p", { class: "modal-text" }, message);
    const cancel = el("button", { class: "ghost" }, "Cancelar");
    const ok = el("button", { class: "pri" }, confirmLabel);
    cancel.onclick = () => {
      overlay.remove();
      resolve(false);
    };
    ok.onclick = () => {
      overlay.remove();
      resolve(true);
    };
    box.append(txt, el("div", { class: "modal-actions" }, cancel, ok));
    overlay.append(box);
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) {
        overlay.remove();
        resolve(false);
      }
    });
    document.body.append(overlay);
    ok.focus();
  });
}

export function promptDialog(message: string, initial = "", confirmLabel = "Salvar"): Promise<string | null> {
  return new Promise((resolve) => {
    const overlay = el("div", { class: "overlay" });
    const box = el("div", { class: "modal", role: "dialog", "aria-modal": "true" });
    const input = el("input", { class: "input", value: initial, maxlength: "80" });
    const cancel = el("button", { class: "ghost" }, "Cancelar");
    const ok = el("button", { class: "pri" }, confirmLabel);
    cancel.onclick = () => {
      overlay.remove();
      resolve(null);
    };
    ok.onclick = () => {
      overlay.remove();
      resolve(input.value);
    };
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") ok.click();
    });
    box.append(el("p", { class: "modal-text" }, message), input, el("div", { class: "modal-actions" }, cancel, ok));
    overlay.append(box);
    document.body.append(overlay);
    input.focus();
    input.select();
  });
}

export function toast(message: string): void {
  const t = el("div", { class: "toast" }, message);
  document.body.append(t);
  setTimeout(() => t.classList.add("show"), 10);
  setTimeout(() => {
    t.classList.remove("show");
    setTimeout(() => t.remove(), 400);
  }, 2200);
}

export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const ta = el("textarea", { class: "visually-hidden" });
    ta.value = text;
    document.body.append(ta);
    ta.select();
    const ok = document.execCommand("copy");
    ta.remove();
    return ok;
  }
}
