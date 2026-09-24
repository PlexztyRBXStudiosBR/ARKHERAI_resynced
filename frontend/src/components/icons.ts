// Ícones próprios do ARKHER: SVG desenhados no projeto (nada de emoji).
// Todos herdam a cor do texto (currentColor) e seguem grade 24x24.

const NS = "http://www.w3.org/2000/svg";

type IconDef = { paths: string[]; circles?: [number, number, number][] };

const DEFS: Record<string, IconDef> = {
  logo: {
    paths: ["M12 2 20 6.8v10.4L12 22l-8-4.8V6.8L12 2z", "M8.6 15.6 12 8.2l3.4 7.4M10 13.2h4"],
  },
  chat: { paths: ["M4 6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H9.5L4 20V6z", "M8 9h8M8 12.5h5"] },
  memory: {
    paths: ["M5 6c0-1.7 3.1-3 7-3s7 1.3 7 3v12c0 1.7-3.1 3-7 3s-7-1.3-7-3V6z", "M5 6c0 1.7 3.1 3 7 3s7-1.3 7-3", "M5 12c0 1.7 3.1 3 7 3s7-1.3 7-3"],
  },
  tools: { paths: ["M20.5 6.5a5 5 0 0 1-6.6 6.2L7 19.6a2.2 2.2 0 0 1-3.1-3.1l6.9-6.9a5 5 0 0 1 6.2-6.6L13.9 6l4.1 4.1 2.5-3.6z"] },
  training: { paths: ["M4 20h16", "M6.5 20v-6.5M11.5 20V6.5M16.5 20V10M21 20V4.5"] },
  settings: {
    paths: ["M12 8.2v-4M12 19.8v-4M8.2 12h-4M19.8 12h-4M9.3 9.3 6.5 6.5M17.5 17.5l-2.8-2.8M14.7 9.3l2.8-2.8M6.5 17.5l2.8-2.8"],
    circles: [[12, 12, 3.2]],
  },
  download: { paths: ["M12 3.5v10.5M12 14l4.2-4.2M12 14 7.8 9.8", "M4.5 20.5h15"] },
  thumbUp: { paths: ["M7 11v9.5H4.5a1 1 0 0 1-1-1v-7.5a1 1 0 0 1 1-1H7zm0 0 3.8-7.2A2 2 0 0 1 13 5.7V9h4.7a2 2 0 0 1 2 2.4l-1.1 6.6a2 2 0 0 1-2 1.7H7"] },
  thumbDown: { paths: ["M17 13V3.5h2.5a1 1 0 0 1 1 1V12a1 1 0 0 1-1 1H17zm0 0-3.8 7.2A2 2 0 0 1 11 18.3V15H6.3a2 2 0 0 1-2-2.4l1.1-6.6a2 2 0 0 1 2-1.7H17"] },
  cube: { paths: ["M12 2.5 19.5 7v10L12 21.5 4.5 17V7L12 2.5z", "M12 21.5V11.5M4.5 7l7.5 4.5L19.5 7"] },
  plug: {
    paths: ["M9 7V3M15 7V3", "M6.5 7h11v3.5a5.5 5.5 0 0 1-11 0V7z", "M12 16v5"],
  },
  chip: {
    paths: ["M8 8h8v8H8z", "M4.5 10h2M4.5 14h2M17.5 10h2M17.5 14h2M10 4.5v2M14 4.5v2M10 17.5v2M14 17.5v2"],
  },
  send: { paths: ["M3.5 11.8 20.5 4l-7.8 17-2.4-7.2-6.8-2z"] },
  close: { paths: ["M6 6l12 12M18 6 6 18"] },
};

export function icon(name: keyof typeof DEFS | string, size = 18): SVGElement {
  const def = DEFS[name] ?? DEFS["cube"];
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("width", String(size));
  svg.setAttribute("height", String(size));
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "1.7");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  svg.setAttribute("class", "ic");
  svg.setAttribute("aria-hidden", "true");
  for (const d of def.paths) {
    const p = document.createElementNS(NS, "path");
    p.setAttribute("d", d);
    svg.appendChild(p);
  }
  for (const [cx, cy, r] of def.circles ?? []) {
    const c = document.createElementNS(NS, "circle");
    c.setAttribute("cx", String(cx));
    c.setAttribute("cy", String(cy));
    c.setAttribute("r", String(r));
    svg.appendChild(c);
  }
  return svg;
}
