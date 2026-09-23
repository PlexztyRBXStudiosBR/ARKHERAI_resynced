"""Construção ao vivo para game dev: stream de operações + temas paramétricos.

A ARKHER descreve construções como uma lista de operações simples
(criar peça com posição/tamanho/cor). Esse stream tem dois destinos:

1. Plugin-ponte no Roblox Studio (o usuário instala e conecta): busca a
   construção pendente e monta tudo peça por peça, em tempo real, dentro
   da place aberta. O usuário controla o programa; a ARKHER constrói.
2. Renderização para .rbxlx (fallback sem plugin): abre direto no Studio.

O mesmo formato de stream servirá de base para os demais conectores
(Blender, Godot etc.). Nada aqui controla a máquina do usuário.
"""
from __future__ import annotations

import math
import random
import secrets
import unicodedata

# ------------------------------------------------------------------ paleta
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


# ------------------------------------------------------- tema: base militar
def base_militar(seed: int = 42) -> list[dict]:
    """Base do exército paramétrica: perímetro, torres, quartéis, heliporto,
    mastro com bandeira, sacos de areia e viaturas. Seed-determinístico."""
    r = random.Random(seed)
    ops: list[dict] = []

    # chão
    _part(ops, "Chao", (0, -0.5, 0), (170, 1, 170), CONCRETO)

    # perímetro com portão na frente (z negativo)
    meia = 80.0
    alt, esp = 6.0, 2.0
    vao = 9.0  # meia-largura do portão
    for nome, x, z, sx, sz in (
        ("MuroTras", 0, meia, 2 * meia, esp),
        ("MuroEsq", -meia, 0, esp, 2 * meia),
        ("MuroDir", meia, 0, esp, 2 * meia),
        ("MuroFrenteEsq", -(meia + vao) / 2, -meia, meia - vao, esp),
        ("MuroFrenteDir", (meia + vao) / 2, -meia, meia - vao, esp),
    ):
        _part(ops, nome, (x, alt / 2, z), (sx, alt, sz), VERDE_ESCURO)

    # torres de vigia nos 4 cantos
    for tx, tz in ((-meia, -meia), (meia, -meia), (-meia, meia), (meia, meia)):
        for i, (lx, lz) in enumerate(((-2.5, -2.5), (2.5, -2.5), (-2.5, 2.5), (2.5, 2.5))):
            _part(ops, f"PernaTorre", (tx + lx, 5, tz + lz), (1, 10, 1), VERDE_OLIVA)
        _part(ops, "PlataformaTorre", (tx, 10.5, tz), (9, 1, 9), VERDE_OLIVA)
        for nome, gx, gz, gsx, gsz in (
            ("GuardaFrente", 0, -4.5, 9, 0.5), ("GuardaTras", 0, 4.5, 9, 0.5),
            ("GuardaEsq", -4.5, 0, 0.5, 9), ("GuardaDir", 4.5, 0, 0.5, 9),
        ):
            _part(ops, nome, (tx + gx, 12, tz + gz), (gsx, 2, gsz), VERDE_OLIVA)
        _part(ops, "TetoTorre", (tx, 14, tz), (10, 0.6, 10), VERDE_ESCURO)

    # portão: pilares + cancela
    _part(ops, "PilarPortaoEsq", (-vao, 4, -meia), (2, 8, 2), CINZA)
    _part(ops, "PilarPortaoDir", (vao, 4, -meia), (2, 8, 2), CINZA)
    _part(ops, "Cancela", (0, 3, -meia), (2 * vao - 2, 0.8, 0.8), AMARELO_BR)

    # quartéis (2 ou 3 conforme a seed), dispostos na metade de trás
    n_quarteis = 2 + r.randint(0, 1)
    for i in range(n_quarteis):
        qx = -45 + i * 45 + r.uniform(-6, 6)
        qz = 30 + r.uniform(-4, 4)
        larg, alt_q, prof = 26.0, 7.0, 12.0
        _part(ops, f"Quartel{i}Piso", (qx, 0.25, qz), (larg, 0.5, prof), CINZA)
        for nome, wx, wz, wsx, wsz in (
            ("Tras", 0, prof / 2, larg, 0.8), ("Esq", -larg / 2, 0, 0.8, prof),
            ("Dir", larg / 2, 0, 0.8, prof),
            ("FrenteEsq", -(larg / 4 + 1.5), -prof / 2, larg / 2 - 3, 0.8),
            ("FrenteDir", (larg / 4 + 1.5), -prof / 2, larg / 2 - 3, 0.8),
        ):
            _part(ops, f"Quartel{i}{nome}", (qx + wx, alt_q / 2, qz + wz), (wsx, alt_q, wsz), CAQUI)
        _part(ops, f"Quartel{i}Teto", (qx, alt_q + 0.3, qz), (larg + 2, 0.6, prof + 2), VERDE_ESCURO)
        _part(ops, f"Quartel{i}Porta", (qx, 3, qz - prof / 2 - 0.1), (3, 6, 0.4), PRETO)

    # centro de comando + antena
    cx, cz = 40 + r.uniform(-5, 5), -10 + r.uniform(-4, 4)
    _part(ops, "ComandoCorpo", (cx, 5, cz), (18, 10, 18), CAQUI)
    _part(ops, "ComandoTeto", (cx, 10.4, cz), (20, 0.8, 20), VERDE_ESCURO)
    _part(ops, "ComandoVidro", (cx, 6, cz - 9.2), (10, 3, 0.4), AZUL_VIDRO)
    _part(ops, "Antena", (cx + 6, 16, cz + 6), (0.6, 12, 0.6), CINZA)
    _part(ops, "AntenaBarra", (cx + 6, 20, cz + 6), (4, 0.4, 0.4), CINZA)

    # heliporto
    hx, hz = -40 + r.uniform(-6, 6), -25 + r.uniform(-4, 4)
    _part(ops, "Heliponto", (hx, 0.3, hz), (22, 0.6, 22), PRETO)
    _part(ops, "HelipontoH1", (hx - 2, 0.65, hz), (1.2, 0.1, 8), BRANCO)
    _part(ops, "HelipontoH2", (hx + 2, 0.65, hz), (1.2, 0.1, 8), BRANCO)
    _part(ops, "HelipontoH3", (hx, 0.65, hz), (4, 0.1, 1.2), BRANCO)

    # mastro + bandeira (verde e amarela) perto do portão
    fx = -14.0
    _part(ops, "Mastro", (fx, 8, -70), (0.5, 16, 0.5), CINZA)
    _part(ops, "BandeiraVerde", (fx + 2.5, 14.5, -70), (5, 3, 0.2), VERDE_BR)
    _part(ops, "BandeiraAmarela", (fx + 2.5, 14.5, -70.15), (2.4, 1.4, 0.2), AMARELO_BR)

    # sacos de areia próximos ao portão
    n_sacos = 10 + r.randint(0, 6)
    for i in range(n_sacos):
        lado = 1 if i % 2 == 0 else -1
        _part(ops, "SacoAreia", (lado * (12 + (i // 2) * 2.2), 0.5 + (i % 3) * 1.0, -74),
              (2, 1, 1.2), CAQUI)

    # viaturas (jeeps de caixas)
    n_jipes = 2 + r.randint(0, 1)
    for i in range(n_jipes):
        jx = 15 + i * 14 + r.uniform(-3, 3)
        jz = -45 + r.uniform(-5, 5)
        giro = r.uniform(-0.4, 0.4)
        _part(ops, f"Jipe{i}Chassi", (jx, 2, jz), (8, 1.6, 4), VERDE_OLIVA)
        _part(ops, f"Jipe{i}Cabine", (jx + 1.5, 3.6, jz), (4, 1.6, 3.8), VERDE_OLIVA)
        _part(ops, f"Jipe{i}Vidro", (jx - 0.6, 3.6, jz), (0.4, 1.2, 3.4), AZUL_VIDRO)
        for wx, wz in ((-2.8, -2.1), (-2.8, 2.1), (2.8, -2.1), (2.8, 2.1)):
            rx = jx + wx * math.cos(giro) - wz * math.sin(giro)
            rz = jz + wx * math.sin(giro) + wz * math.cos(giro)
            _part(ops, f"Jipe{i}Roda", (rx, 1, rz), (1.2, 2, 2), PRETO)

    return ops


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", (t or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))


TEMAS = {
    "militar": ("Base militar do exército", base_militar),
}


def normalizar_tema(tema: str) -> str:
    """Resolve 'base do exercito brasileiro', 'militar' etc → tema registrado."""
    t = _norm(tema)
    if not t:
        raise ValueError("Tema vazio.")
    for chave in TEMAS:
        if chave in t:
            return chave
    if "exercito" in t or "guerra" in t or "forte" in t or "base" in t:
        return "militar"
    raise ValueError(f"Tema desconhecido. Opções: {', '.join(sorted(TEMAS))}")


def criar_build(user_id: str, tema: str, seed: int = 42) -> dict:
    """Gera a construção e registra um build pendente para o plugin buscar."""
    chave = normalizar_tema(tema)
    ops = TEMAS[chave][1](seed)
    build_id = "b_" + secrets.token_hex(6)
    _BUILDS[build_id] = {"user_id": user_id, "tema": chave, "seed": seed, "ops": ops}
    return {"build_id": build_id, "tema": chave, "seed": seed, "ops": ops}


def build_pendente(user_id: str) -> dict | None:
    """Build mais recente do usuário (para o plugin-ponte buscar)."""
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
