// Visualizador 3D: o parser OBJ precisa ler exatamente o formato que o
// backend gera (v x y z + f a b c d, 1-indexado).
import { describe, it, expect } from "vitest";
import { parseObj } from "../src/components/viewer3d";

const OBJ_EXEMPLO = [
  "# Terreno ARKHER — seed 1, grade 3x3",
  "v 0.00 0.500 0.00",
  "v 1.00 -0.250 0.00",
  "v 2.00 0.100 0.00",
  "v 0.00 0.000 1.00",
  "v 1.00 0.750 1.00",
  "v 2.00 -0.100 1.00",
  "v 0.00 0.200 2.00",
  "v 1.00 0.050 2.00",
  "v 2.00 0.400 2.00",
  "f 1 2 5 4",
  "f 2 3 6 5",
  "f 4 5 8 7",
  "f 5 6 9 8",
].join("\n");

describe("parseObj", () => {
  it("lê vértices e faces no formato gerado pelo backend", () => {
    const d = parseObj(OBJ_EXEMPLO);
    expect(d).not.toBeNull();
    expect(d!.pos.length).toBe(9 * 3);
    // 4 quads → 8 triângulos → 24 índices
    expect(d!.idx.length).toBe(8 * 3);
    expect(d!.altMin).toBeCloseTo(-0.25);
    expect(d!.altMax).toBeCloseTo(0.75);
  });

  it("índices são convertidos de 1-based para 0-based", () => {
    const d = parseObj(OBJ_EXEMPLO)!;
    expect(Math.min(...Array.from(d.idx))).toBe(0);
    expect(Math.max(...Array.from(d.idx))).toBe(8);
  });

  it("rejeita conteúdo sem geometria", () => {
    expect(parseObj("# só comentário")).toBeNull();
    expect(parseObj("")).toBeNull();
  });
});
