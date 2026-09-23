"""Construção ao vivo para game dev: compositor aberto + stream de operações.

Nada de lista fixa de temas: a ARKHER interpreta o pedido em linguagem
natural (estruturas + quantidades) e compõe a construção peça por peça.
O stream de operações tem dois destinos:

1. Plugin-ponte no Roblox Studio: busca a construção pendente e monta tudo
   em tempo real dentro da place aberta.
2. Addon-ponte no Blender: cria as peças como meshes reais, com material e
   cor, dentro da cena aberta — modelagem de verdade.

O usuário controla os programas; a ARKHER constrói. Sem controle de máquina.
"""
from __future__ import annotations

import math
import random
import re
import secrets
import unicodedata

# ------------------------------------------------------------------ paletas
VERDE_OLIVA = (75, 83, 32)
CAQUI = (194, 178, 128)
CONCRETO = (160, 158, 150)
CINZA = (110, 110, 110)
VERDE_ESCURO = (34, 60, 34)
VERDE_BR = (0, 156, 59)
AMARELO_BR = (255, 211, 0)
BRANCO = (245, 245, 245)
PRETO = (30, 30, 30)
AZUL_VIDRO = (150, 190, 220)
MARROM = (101, 67, 33)
VERDE_FOLHA = (52, 120, 48)
AREIA = (222, 202, 150)

PALETAS = {
    "militar": {"parede": CAQUI, "teto": VERDE_ESCURO, "piso": CONCRETO,
                "estrutura": VERDE_OLIVA, "detalhe": CINZA, "vidro": AZUL_VIDRO,
                "veiculo": VERDE_OLIVA, "destaque1": VERDE_BR, "destaque2": AMARELO_BR,
                "chao": AREIA},
    "cidade": {"parede": (200, 200, 205), "teto": (90, 95, 105), "piso": CINZA,
               "estrutura": CINZA, "detalhe": (70, 70, 75), "vidro": AZUL_VIDRO,
               "veiculo": (160, 40, 40), "destaque1": BRANCO, "destaque2": AMARELO_BR,
               "chao": (130, 130, 135)},
    "padrao": {"parede": (190, 185, 170), "teto": (120, 100, 90), "piso": CONCRETO,
               "estrutura": CINZA, "detalhe": CINZA, "vidro": AZUL_VIDRO,
               "veiculo": CINZA, "destaque1": BRANCO, "destaque2": AMARELO_BR,
               "chao": (150, 160, 130)},
}

# registro em memória: build_id -> {"user_id","tema","seed","ops"}
_BUILDS: dict[str, dict] = {}


def _part(ops: list, nome: str, pos, size, cor, ancorado: bool = True) -> None:
    ops.append({
        "op": "part",
        "nome": nome,
        "pos": [float(v) for v in pos],
        "size": [float(v) for v in size],
        "cor": [int(c) for c in cor],
        "ancorado": ancorado,
    })


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", (t or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))


# ------------------------------------------------------------- estruturas
def _torre(ops, r, x, z, p) -> None:
    for lx, lz in ((-2.5, -2.5), (2.5, -2.5), (-2.5, 2.5), (2.5, 2.5)):
        _part(ops, "PernaTorre", (x + lx, 5, z + lz), (1, 10, 1), p["estrutura"])
    _part(ops, "PlataformaTorre", (x, 10.5, z), (9, 1, 9), p["estrutura"])
    for gx, gz, gsx, gsz in ((0, -4.5, 9, 0.5), (0, 4.5, 9, 0.5), (-4.5, 0, 0.5, 9), (4.5, 0, 0.5, 9)):
        _part(ops, "GuardaTorre", (x + gx, 12, z + gz), (gsx, 2, gsz), p["estrutura"])
    _part(ops, "TetoTorre", (x, 14, z), (10, 0.6, 10), p["teto"])


def _predio(ops, r, x, z, p, nome="Predio", lar=26.0, alt=7.0, prof=12.0) -> None:
    _part(ops, f"{nome}Piso", (x, 0.25, z), (lar, 0.5, prof), p["piso"])
    for wx, wz, wsx, wsz in (
        (0, prof / 2, lar, 0.8), (-lar / 2, 0, 0.8, prof), (lar / 2, 0, 0.8, prof),
        (-(lar / 4 + 1.5), -prof / 2, lar / 2 - 3, 0.8), ((lar / 4 + 1.5), -prof / 2, lar / 2 - 3, 0.8),
    ):
        _part(ops, f"{nome}Parede", (x + wx, alt / 2, z + wz), (wsx, alt, wsz), p["parede"])
    _part(ops, f"{nome}Teto", (x, alt + 0.3, z), (lar + 2, 0.6, prof + 2), p["teto"])
    _part(ops, f"{nome}Porta", (x, 3, z - prof / 2 - 0.1), (3, 6, 0.4), PRETO)
    _part(ops, f"{nome}Janela", (x - lar / 4, 4.5, z - prof / 2 - 0.1), (2.5, 2, 0.3), p["vidro"])
    _part(ops, f"{nome}Janela2", (x + lar / 4, 4.5, z - prof / 2 - 0.1), (2.5, 2, 0.3), p["vidro"])


def _casa(ops, r, x, z, p) -> None:
    _predio(ops, r, x, z, p, nome="Casa", lar=12.0, alt=5.0, prof=10.0)


def _arvore(ops, r, x, z, p) -> None:
    a = r.uniform(0.8, 1.3)
    _part(ops, "Tronco", (x, 3 * a, z), (1.2 * a, 6 * a, 1.2 * a), MARROM)
    _part(ops, "Copa", (x, 7 * a, z), (5 * a, 4 * a, 5 * a), VERDE_FOLHA)


def _heliponto(ops, r, x, z, p) -> None:
    _part(ops, "Heliponto", (x, 0.3, z), (22, 0.6, 22), PRETO)
    _part(ops, "HelipontoH1", (x - 2, 0.65, z), (1.2, 0.1, 8), BRANCO)
    _part(ops, "HelipontoH2", (x + 2, 0.65, z), (1.2, 0.1, 8), BRANCO)
    _part(ops, "HelipontoH3", (x, 0.65, z), (4, 0.1, 1.2), BRANCO)


def _mastro(ops, r, x, z, p) -> None:
    _part(ops, "Mastro", (x, 8, z), (0.5, 16, 0.5), p["detalhe"])
    _part(ops, "BandeiraA", (x + 2.5, 14.5, z), (5, 3, 0.2), p["destaque1"])
    _part(ops, "BandeiraB", (x + 2.5, 14.5, z - 0.15), (2.4, 1.4, 0.2), p["destaque2"])


def _antena(ops, r, x, z, p) -> None:
    _part(ops, "Antena", (x, 6, z), (0.6, 12, 0.6), p["detalhe"])
    _part(ops, "AntenaBarra", (x, 10, z), (4, 0.4, 0.4), p["detalhe"])


def _veiculo(ops, r, x, z, p) -> None:
    giro = r.uniform(-0.5, 0.5)
    _part(ops, "VeiculoChassi", (x, 2, z), (8, 1.6, 4), p["veiculo"])
    _part(ops, "VeiculoCabine", (x + 1.5, 3.6, z), (4, 1.6, 3.8), p["veiculo"])
    _part(ops, "VeiculoVidro", (x - 0.6, 3.6, z), (0.4, 1.2, 3.4), p["vidro"])
    for wx, wz in ((-2.8, -2.1), (-2.8, 2.1), (2.8, -2.1), (2.8, 2.1)):
        rx = x + wx * math.cos(giro) - wz * math.sin(giro)
        rz = z + wx * math.sin(giro) + wz * math.cos(giro)
        _part(ops, "VeiculoRoda", (rx, 1, rz), (1.2, 2, 2), PRETO)


def _sacos(ops, r, x, z, p) -> None:
    n = 8 + r.randint(0, 6)
    for i in range(n):
        _part(ops, "SacoAreia", (x + (i % 5) * 2.2, 0.5 + (i // 5) * 1.0, z + (i % 2) * 1.3),
              (2, 1, 1.2), CAQUI)


def _muro_perimetro(ops, meia, p) -> int:
    alt, esp, vao = 6.0, 2.0, 9.0
    segs = [
        ("MuroTras", 0, meia, 2 * meia, esp),
        ("MuroEsq", -meia, 0, esp, 2 * meia),
        ("MuroDir", meia, 0, esp, 2 * meia),
        ("MuroFrenteEsq", -(meia + vao) / 2, -meia, meia - vao, esp),
        ("MuroFrenteDir", (meia + vao) / 2, -meia, meia - vao, esp),
    ]
    for nome, x, z, sx, sz in segs:
        _part(ops, nome, (x, alt / 2, z), (sx, alt, sz), p["teto"])
    _part(ops, "PilarPortaoEsq", (-vao, 4, -meia), (2, 8, 2), p["detalhe"])
    _part(ops, "PilarPortaoDir", (vao, 4, -meia), (2, 8, 2), p["detalhe"])
    _part(ops, "Cancela", (0, 3, -meia), (2 * vao - 2, 0.8, 0.8), p["destaque2"])
    return len(segs) + 3


ESTRUTURAS = {
    "torre": {"funcao": _torre, "chaves": ("torre", "torres", "vigia"), "raio": 8},
    "quartel": {"funcao": lambda o, r, x, z, p: _predio(o, r, x, z, p, "Quartel"), "chaves": ("quartel", "quarteis"), "raio": 17},
    "predio": {"funcao": lambda o, r, x, z, p: _predio(o, r, x, z, p, "Predio", 16, 12, 14), "chaves": ("predio", "predios"), "raio": 12},
    "casa": {"funcao": _casa, "chaves": ("casa", "casas"), "raio": 9},
    "arvore": {"funcao": _arvore, "chaves": ("arvore", "arvores", "floresta"), "raio": 4},
    "heliponto": {"funcao": _heliponto, "chaves": ("heliponto", "heliporto"), "raio": 13},
    "mastro": {"funcao": _mastro, "chaves": ("mastro", "bandeira"), "raio": 3},
    "antena": {"funcao": _antena, "chaves": ("antena", "radar"), "raio": 3},
    "veiculo": {"funcao": _veiculo, "chaves": ("veiculo", "veiculos", "jipe", "jipes", "carro", "carros"), "raio": 6},
    "sacos": {"funcao": _sacos, "chaves": ("sacos", "trincheira"), "raio": 7},
}

_NUMEROS = {"um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4,
            "cinco": 5, "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10}


def interpretar(texto: str) -> dict[str, int]:
    """Extrai estruturas e quantidades do pedido em linguagem natural."""
    t = _norm(texto)
    receita: dict[str, int] = {}
    for nome, spec in ESTRUTURAS.items():
        qtd = 0
        for chave in spec["chaves"]:
            for m in re.finditer(rf"(\d{{1,2}}|{'|'.join(_NUMEROS)})\s+(?:de\s+)?{chave}\b", t):
                tok = m.group(1)
                qtd = max(qtd, int(tok) if tok.isdigit() else _NUMEROS.get(tok, 1))
            if qtd == 0 and re.search(rf"\b{chave}\b", t):
                qtd = max(qtd, 1)
        if qtd:
            receita[nome] = qtd
    return receita


def paleta_para(texto: str) -> str:
    t = _norm(texto)
    if "militar" in t or "exercito" in t or "guerra" in t or "quartel" in t:
        return "militar"
    if "cidade" in t or "vila" in t or "urbana" in t or "rua" in t:
        return "cidade"
    return "padrao"


RECEITA_MILITAR = {"quartel": 3, "torre": 4, "heliponto": 1, "mastro": 1,
                    "antena": 1, "veiculo": 3, "sacos": 1}


def compor_receita(receita: dict[str, int], seed: int = 42, paleta: str = "padrao",
                   com_muro: bool = False) -> list[dict]:
    """Compõe a construção: chão, perímetro opcional e itens em espiral."""
    r = random.Random(seed)
    p = PALETAS.get(paleta, PALETAS["padrao"])
    ops: list[dict] = []

    itens: list[str] = []
    for nome, qtd in receita.items():
        itens.extend([nome] * max(0, min(qtd, 40)))
    n = len(itens)
    meia = max(32.0, 10.0 * math.sqrt(n) + 24.0)
    _part(ops, "Chao", (0, -0.5, 0), (2 * meia + 10, 1, 2 * meia + 10), p["chao"])
    if com_muro:
        _muro_perimetro(ops, meia, p)

    ang = r.uniform(0, math.tau)
    for i, nome in enumerate(itens):
        spec = ESTRUTURAS[nome]
        raio = 12.0 + 7.0 * math.sqrt(i) if i else 0.0
        a = ang + i * 2.399963229728653  # ângulo dourado: espalha sem sobrepor
        x = raio * math.cos(a) + r.uniform(-2, 2)
        z = raio * math.sin(a) + r.uniform(-2, 2)
        spec["funcao"](ops, r, x, z, p)
    return ops


def compor(texto: str, seed: int = 42) -> list[dict]:
    """Interpreta o pedido livre e compõe. ValueError se nada for reconhecido."""
    t = _norm(texto)
    if "militar" in t or "exercito" in t:
        return compor_receita(RECEITA_MILITAR, seed, "militar", com_muro=True)
    receita = interpretar(texto)
    if not receita:
        raise ValueError(
            "Não reconheci estruturas no pedido. Posso construir: "
            + ", ".join(sorted(ESTRUTURAS))
            + " (ex.: '3 torres, 2 quartéis, heliponto e veículos')."
        )
    com_muro = bool(re.search(r"\b(muro|muralha|cerco|perimetro|forte)\b", t))
    return compor_receita(receita, seed, paleta_para(texto), com_muro=com_muro)


def base_militar(seed: int = 42) -> list[dict]:
    """Receita militar clássica (mantida por compatibilidade)."""
    return compor_receita(RECEITA_MILITAR, seed, "militar", com_muro=True)


def criar_build(user_id: str, tema: str, seed: int = 42) -> dict:
    """Gera a construção e registra um build pendente para as pontes buscarem."""
    tema = (tema or "").strip()
    if not tema:
        raise ValueError("Tema vazio.")
    ops = compor(tema, seed)
    build_id = "b_" + secrets.token_hex(6)
    _BUILDS[build_id] = {"user_id": user_id, "tema": tema[:120], "seed": seed, "ops": ops}
    return {"build_id": build_id, "tema": tema[:120], "seed": seed, "ops": ops}


def build_pendente(user_id: str) -> dict | None:
    """Build mais recente do usuário (para as pontes buscarem)."""
    ultimo = None
    for bid, b in _BUILDS.items():
        if b["user_id"] == user_id:
            ultimo = {"build_id": bid, **b}
    if ultimo is not None:
        ultimo.pop("user_id", None)
    return ultimo


def obter_build(user_id: str, build_id: str) -> dict | None:
    b = _BUILDS.get(build_id)
    if b is None or b["user_id"] != user_id:
        return None
    return {"build_id": build_id, "tema": b["tema"], "seed": b["seed"], "ops": b["ops"]}
