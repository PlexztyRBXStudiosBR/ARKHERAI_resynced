// Markdown mínimo e sanitizado. Estratégia: escapar TODO o HTML primeiro e
// depois aplicar um subconjunto seguro de formatação. Nenhum HTML cru passa.

function escapeHtml(s: string): string {
  return s
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function inline(s: string): string {
  return s
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[\s(])\*([^*\n]+)\*(?=[\s).,!?:;]|$)/g, "$1<em>$2</em>")
    .replace(
      /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>',
    );
}

export interface RenderedBlock {
  html: string;
  codes: string[]; // conteúdos dos blocos de código (para botões de copiar)
}

export function renderMarkdown(src: string): RenderedBlock {
  const codes: string[] = [];
  const lines = escapeHtml(src).split("\n");
  const out: string[] = [];
  let i = 0;
  let inList = false;

  const closeList = () => {
    if (inList) {
      out.push("</ul>");
      inList = false;
    }
  };

  while (i < lines.length) {
    const line = lines[i];
    const fence = line.match(/^```(\w*)$/);
    if (fence) {
      closeList();
      const buf: string[] = [];
      i++;
      while (i < lines.length && !/^```/.test(lines[i])) {
        buf.push(lines[i]);
        i++;
      }
      i++; // fecha a cerca
      const code = buf.join("\n");
      codes.push(code);
      const codeIdx = codes.length - 1;
      out.push(
        `<div class="codeblock"><div class="codebar"><span>${fence[1] || "código"}</span>` +
          `<button class="copycode" data-code="${codeIdx}">copiar</button></div>` +
          `<pre><code>${code || " "}</code></pre></div>`,
      );
      continue;
    }
    const h = line.match(/^(#{1,3})\s+(.*)$/);
    if (h) {
      closeList();
      out.push(`<h${h[1].length}>${inline(h[2])}</h${h[1].length}>`);
      i++;
      continue;
    }
    if (/^\s*[-*]\s+/.test(line)) {
      if (!inList) {
        out.push("<ul>");
        inList = true;
      }
      out.push(`<li>${inline(line.replace(/^\s*[-*]\s+/, ""))}</li>`);
      i++;
      continue;
    }
    if (/^\s*\d+\.\s+/.test(line)) {
      closeList();
      out.push(`<p>${inline(line)}</p>`);
      i++;
      continue;
    }
    if (line.trim() === "") {
      closeList();
      i++;
      continue;
    }
    closeList();
    out.push(`<p>${inline(line)}</p>`);
    i++;
  }
  closeList();
  return { html: out.join("\n"), codes };
}

export function stripHtmlForCopy(src: string): string {
  return src;
}
