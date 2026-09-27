"""JPG de cena inteira (conceito), não tile de textura. Sem modelo de terceiro."""
from __future__ import annotations

import base64
import math
import random
import unicodedata

from backend.app.tools.jpeg import encode_jpeg


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", (t or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def _clamp(v: int) -> int:
    return 0 if v < 0 else 255 if v > 255 else v


def gerar_jpg(pedido: str = "atelier", seed: int | str | None = 42, largura: int = 960, altura: int = 540) -> dict:
    semente = int(seed) if seed not in (None, "") else 42
    rng = random.Random(semente)
    n = _norm(pedido)
    w = max(320, min(1280, int(largura)))
    h = max(180, min(720, int(altura)))
    if "noite" in n or "lua" in n:
        ceu, chao, acento = (18, 22, 48), (28, 24, 20), (200, 190, 140)
    elif "lava" in n or "magma" in n:
        ceu, chao, acento = (40, 12, 8), (50, 18, 10), (220, 90, 20)
    elif "neve" in n or "inverno" in n:
        ceu, chao, acento = (186, 198, 214), (220, 224, 230), (90, 110, 140)
    elif "floresta" in n or "mato" in n:
        ceu, chao, acento = (70, 110, 150), (34, 72, 38), (20, 40, 18)
    else:
        ceu, chao, acento = (120, 96, 70), (42, 34, 26), (196, 163, 90)
    rgb = bytearray(w * h * 3)
    hz = int(h * 0.58)
    solx, soly = int(w * (0.18 + (semente % 40) / 100)), int(h * 0.22)
    for y in range(h):
        t = y / max(1, h - 1)
        for x in range(w):
            i = (y * w + x) * 3
            if y < hz:
                nuv = 12 * math.sin(x * 0.02 + semente) * math.sin(y * 0.04)
                r = ceu[0] + int((255 - ceu[0]) * (1 - t) * 0.25) + int(nuv)
                g = ceu[1] + int(nuv * 0.6)
                b = ceu[2] + int((80 - t * 40))
            else:
                gnd = (y - hz) / max(1, h - hz)
                r = int(chao[0] * (1 - 0.35 * gnd))
                g = int(chao[1] * (1 - 0.25 * gnd))
                b = int(chao[2] * (1 - 0.2 * gnd))
                if (x + y + semente) % 17 == 0:
                    r, g, b = r + 8, g + 6, b + 4
            dx, dy = x - solx, y - soly
            if dx * dx + dy * dy < 420:
                r, g, b = acento[0], acento[1], acento[2]
            rgb[i], rgb[i + 1], rgb[i + 2] = _clamp(r), _clamp(g), _clamp(b)
    # marcos (silhueta, não predio-template grid)
    nmarc = 3 + (semente % 4)
    for k in range(nmarc):
        mx = int(w * (0.2 + 0.6 * ((k * 37 + semente) % 100) / 100))
        mw = 18 + (k * 11 + semente) % 40
        mh = 40 + (k * 23 + semente) % 90
        for y in range(hz - mh, hz):
            if y < 0:
                continue
            for x in range(mx, min(w, mx + mw)):
                i = (y * w + x) * 3
                rgb[i] = _clamp(acento[0] // 3 + rng.randint(0, 8))
                rgb[i + 1] = _clamp(acento[1] // 4)
                rgb[i + 2] = _clamp(acento[2] // 5)
    jpg = encode_jpeg(w, h, bytes(rgb), 80)
    return {
        "descricao": f"JPG {w}×{h} de '{pedido[:80]}' (seed {semente}) — cena inteira gerada pela ARKHER, sem modelo de terceiro.",
        "como_usar": "Abre no chat, baixa o .jpg, usa de conceito no Godot (Sky/Environment) ou referência no Blender.",
        "arquivo": {
            "nome": f"arkher_cena_{semente}.jpg",
            "conteudo_b64": base64.b64encode(jpg).decode("ascii"),
        },
    }
