import { describe, expect, it } from "vitest";
import { renderMarkdown } from "../src/app/md";

describe("markdown sanitizado", () => {
  it("escapa HTML cru (sem injeção)", () => {
    const { html } = renderMarkdown('<script>alert("x")</script><img src=x onerror=alert(1)>');
    expect(html).not.toContain("<script>");
    expect(html).not.toContain("<img");
    expect(html).toContain("&lt;script&gt;");
  });

  it("não permite javascript: em links", () => {
    const { html } = renderMarkdown("[clique](javascript:alert(1))");
    expect(html).not.toContain("href=\"javascript:");
  });

  it("permite apenas http/https em links, com noopener", () => {
    const { html } = renderMarkdown("[docs](https://example.org/a)");
    expect(html).toContain('href="https://example.org/a"');
    expect(html).toContain('rel="noopener noreferrer"');
  });

  it("renderiza blocos de código e expõe o conteúdo para copiar", () => {
    const { html, codes } = renderMarkdown("```js\nconst a = 1;\n```");
    expect(html).toContain("<pre><code>");
    expect(codes[0]).toBe("const a = 1;");
    expect(html).toContain("copycode");
  });

  it("renderiza formatação básica", () => {
    const { html } = renderMarkdown("# Título\n**forte** e *ênfase* e `código`\n- item");
    expect(html).toContain("<h1>Título</h1>");
    expect(html).toContain("<strong>forte</strong>");
    expect(html).toContain("<em>ênfase</em>");
    expect(html).toContain("<code>código</code>");
    expect(html).toContain("<li>item</li>");
  });

  it("neutraliza atributos forjados em texto", () => {
    const { html } = renderMarkdown('a "b" \'c\' & <div onload="x()">');
    expect(html).not.toContain("<div");
    // "onload=" só pode existir como texto escapado, nunca como atributo real
    expect(html).not.toMatch(/<\s*div[^>]*onload=/);
    expect(html).toContain("&lt;div");
  });
});
