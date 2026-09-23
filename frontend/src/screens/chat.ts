// Tela principal: conversa com a ARKHER (backend + modelo próprios).

import { renderMarkdown } from "../app/md";
import { confirmDialog, copyText, el, promptDialog, toast } from "../components/ui";
import type { ApiError, Message } from "../services/api";
import { t } from "../services/i18n";
import type { Ctx } from "../app/app";

const EXAMPLES = [
  "Crie uma base do exército no Roblox Studio",
  "Crie um obby no Roblox Studio",
  "Crie um personagem 3D no Blender",
  "Gere um terreno com montanhas",
];

export function renderChat(ctx: Ctx): HTMLElement {
  const root = el("div", { class: "chat-layout" });
  const sidebar = renderSidebar(ctx);
  const main = el("div", { class: "chat-main" });
  main.append(renderMessages(ctx), renderComposer(ctx));
  root.append(sidebar, main);
  return root;
}

function renderSidebar(ctx: Ctx): HTMLElement {
  const s = ctx.store.state;
  const lang = s.settings.lang;
  const aside = el("aside", { class: "sidebar" });
  const newBtn = el("button", { class: "pri wide" }, "+ " + t("new_chat", lang));
  newBtn.onclick = async () => {
    ctx.store.set({ currentSessionId: null, messages: [], streamingContent: "" });
    try {
      await ctx.api.sessions(); // apenas valida backend
    } catch {
      /* estado já refletido pelo polling */
    }
  };
  aside.append(newBtn);
  const list = el("div", { class: "session-list" });
  for (const sess of s.sessions) {
    const item = el("div", { class: "session-item" + (sess.id === s.currentSessionId ? " on" : "") });
    const title = el("span", { class: "session-title" }, sess.title);
    title.onclick = () => void ctx.openSession(sess.id);
    const actions = el("span", { class: "session-actions" });
    const ren = el("button", { class: "mini", title: t("rename", lang) }, "✎");
    ren.onclick = async (e) => {
      e.stopPropagation();
      const novo = await promptDialog(t("rename", lang) + "?", sess.title);
      if (novo && novo.trim()) {
        await ctx.api.renameSession(sess.id, novo.trim());
        await ctx.refreshSessions();
      }
    };
    const del = el("button", { class: "mini danger", title: t("delete", lang) }, "🗑");
    del.onclick = async (e) => {
      e.stopPropagation();
      if (await confirmDialog(t("confirm_delete_chat", lang), t("delete", lang))) {
        await ctx.api.deleteSession(sess.id);
        if (s.currentSessionId === sess.id) ctx.store.set({ currentSessionId: null, messages: [] });
        await ctx.refreshSessions();
      }
    };
    actions.append(ren, del);
    item.append(title, actions);
    list.append(item);
  }
  aside.append(list);
  return aside;
}

function statusBanner(ctx: Ctx): HTMLElement | null {
  const s = ctx.store.state;
  const lang = s.settings.lang;
  if (s.ui === "ready") {
    const b = el("div", { class: "banner info" }, t("model_quality_note", lang));
    return b;
  }
  if (s.ui === "backend_ready_model_missing" || s.ui === "error") {
    return el("div", { class: "banner warn" }, t("err_model", lang));
  }
  if (s.ui === "offline") {
    return el("div", { class: "banner err" }, t("err_backend", lang));
  }
  if (s.ui === "model_loading") {
    return el("div", { class: "banner info" }, t("status_model_loading", lang) + "…");
  }
  return null;
}

function renderMessages(ctx: Ctx): HTMLElement {
  const s = ctx.store.state;
  const lang = s.settings.lang;
  const box = el("div", { class: "messages", id: "messages" });

  const banner = statusBanner(ctx);
  if (banner) box.append(banner);

  if (s.messages.length === 0 && !s.streamingContent) {
    const empty = el("div", { class: "empty-state" });
    empty.append(
      el("div", { class: "empty-logo" }, "◆"),
      el("h1", {}, "ARKHER AI"),
      el("p", { class: "tagline" }, t("tagline", lang)),
      el("p", { class: "intro" }, t("intro", lang)),
      el("h2", {}, t("examples", lang)),
    );
    const chips = el("div", { class: "chips" });
    for (const ex of EXAMPLES) {
      const c = el("button", { class: "chip" }, ex);
      c.onclick = () => void ctx.send(ex);
      chips.append(c);
    }
    empty.append(chips);
    box.append(empty);
    return box;
  }

  for (const m of s.messages) box.append(messageEl(ctx, m, false));

  if (s.streamingContent) {
    box.append(messageEl(ctx, { role: "assistant", content: s.streamingContent, kind: "streaming", created_at: "" }, true));
  } else if (s.ui === "generating") {
    box.append(el("div", { class: "msg assistant" }, el("div", { class: "msg-bubble" }, el("span", { class: "typing" }, "ARKHER ▍"))));
  }
  box.scrollTop = box.scrollHeight;
  return box;
}

function messageEl(ctx: Ctx, m: Message, streaming: boolean): HTMLElement {
  const s = ctx.store.state;
  const lang = s.settings.lang;
  const wrap = el("div", { class: `msg ${m.role}` + (m.kind === "recusa" ? " refusal" : "") });
  const bubble = el("div", { class: "msg-bubble" });
  const rendered = renderMarkdown(m.content);
  const body = el("div", { class: "msg-body" });
  body.innerHTML = rendered.html;
  bubble.append(body);

  // copiar blocos de código
  bubble.querySelectorAll<HTMLButtonElement>("button.copycode").forEach((btn) => {
    btn.onclick = async () => {
      const idx = Number(btn.dataset["code"]);
      await copyText(rendered.codes[idx] ?? "");
      btn.textContent = t("copied", lang);
      setTimeout(() => (btn.textContent = t("copy", lang)), 1500);
    };
    btn.textContent = t("copy", lang);
  });

  if (!streaming) {
    const actions = el("div", { class: "msg-actions" });
    const copy = el("button", { class: "mini" }, t("copy", lang));
    copy.onclick = async () => {
      await copyText(m.content);
      toast(t("copied", lang));
    };
    actions.append(copy);
    if (m.role === "user") {
      const edit = el("button", { class: "mini" }, t("edit", lang));
      edit.onclick = async () => {
        const novo = await promptDialog(t("edit", lang) + "?", m.content);
        if (novo && novo.trim()) await ctx.send(novo.trim(), true);
      };
      actions.append(edit);
    } else if (m.role === "assistant" && s.ui !== "generating") {
      const isLastAssistant = [...s.messages].reverse().find((x) => x.role === "assistant") === m;
      if (isLastAssistant) {
        const regen = el("button", { class: "mini" }, t("regenerate", lang));
        regen.onclick = () => void ctx.regenerate();
        actions.append(regen);
      }
      if (m.hash) {
        const up = el("button", { class: "mini", title: "Boa resposta — ajuda o treino" }, "👍");
        up.onclick = () => void ctx.rate(m.hash!, 1, up);
        const down = el("button", { class: "mini", title: "Resposta ruim — ajuda o treino" }, "👎");
        down.onclick = () => void ctx.rate(m.hash!, -1, down);
        actions.append(up, down);
      }
      if (m.arquivo) {
        const dl = el("button", { class: "mini pri" }, "⤓ baixar " + m.arquivo.nome);
        dl.onclick = () => ctx.download(m.arquivo!.nome, m.arquivo!.conteudo ?? "", m.arquivo!.conteudo_b64);
        actions.append(dl);
      }
    }
    wrap.append(bubble, actions);
  } else {
    wrap.append(bubble);
  }
  return wrap;
}

function renderComposer(ctx: Ctx): HTMLElement {
  const s = ctx.store.state;
  const lang = s.settings.lang;
  const bar = el("div", { class: "composer" });
  const input = el("textarea", {
    class: "input",
    id: "composer-input",
    rows: "2",
    maxlength: "4000",
    placeholder: t("placeholder", lang),
  });
  input.value = ctx.draft;
  input.addEventListener("input", () => (ctx.draft = input.value));
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void ctx.send(input.value);
    }
  });

  const send = el("button", { class: "pri", id: "send-btn" }, t("send", lang));
  send.disabled = s.ui === "generating";
  send.onclick = () => void ctx.send(input.value);

  const cancel = el("button", { class: "danger" }, t("cancel", lang));
  cancel.onclick = () => void ctx.cancel();

  const exportBtn = el("button", { class: "ghost", title: t("export_chat", lang) }, "⤓");
  exportBtn.onclick = () => ctx.exportSession();

  bar.append(input, el("div", { class: "composer-btns" }, s.ui === "generating" ? cancel : send, exportBtn));
  return bar;
}

export function afterChatRender(ctx: Ctx): void {
  const input = document.getElementById("composer-input") as HTMLTextAreaElement | null;
  if (input && ctx.focusComposer) {
    input.focus();
    ctx.focusComposer = false;
  }
}

export type { ApiError };
