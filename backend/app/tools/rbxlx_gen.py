"""Geração de places nativos do Roblox Studio (.rbxlx).

A ARKHER gera o arquivo no formato XML oficial (version 4, o mesmo que o
Studio salva): o usuário baixa e abre direto no Roblox Studio — nada de
colar código, a cena já vem construída. Formato conforme a especificação
pública RobloxAPI/spec (rbxlx) e rojo-rbx/rbx-dom.

Determinístico por seed; sem rede, sem dependências externas.
"""
from __future__ import annotations

import math
import random
from xml.sax.saxutils import escape, quoteattr

_PLACES = ("obby", "arena", "base")

_CABECALHO = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    "<roblox version=\"4\">\n"
)


def _cf(x: float, y: float, z: float) -> str:
    """CoordinateFrame identidade transladada (formato oficial rbxlx)."""
    return (
        f"<X>{x:g}</X><Y>{y:g}</Y><Z>{z:g}</Z>"
        "<R00>1</R00><R01>0</R01><R02>0</R02>"
        "<R10>0</R10><R11>1</R11><R12>0</R12>"
        "<R20>0</R20><R21>0</R21><R22>1</R22>"
    )


class _Ref:
    def __init__(self) -> None:
        self.n = 0

    def novo(self) -> str:
        self.n += 1
        return f"RBX{self.n:04d}"


def _part(ref: str, nome: str, x: float, y: float, z: float,
          sx: float, sy: float, sz: float, cor: int | None = None,
          ancorado: bool = True, children: str = "") -> str:
    props = (
        f"<string name=\"Name\">{escape(nome)}</string>"
        f"<bool name=\"Anchored\">{'true' if ancorado else 'false'}</bool>"
        f"<bool name=\"CanCollide\">true</bool>"
        f"<Vector3 name=\"size\"><X>{sx:g}</X><Y>{sy:g}</Y><Z>{sz:g}</Z></Vector3>"
        f"<CoordinateFrame name=\"CFrame\">{_cf(x, y, z)}</CoordinateFrame>"
    )
    if cor is not None:
        props += f"<Color3uint8 name=\"Color\">{cor}</Color3uint8>"
    return (
        f"<Item class=\"Part\" referent={quoteattr(ref)}>"
        f"<Properties>{props}</Properties>{children}</Item>\n"
    )


def _spawn(ref: str, nome: str, x: float, y: float, z: float, cor: int) -> str:
    return (
        f"<Item class=\"SpawnLocation\" referent={quoteattr(ref)}>"
        "<Properties>"
        f"<string name=\"Name\">{escape(nome)}</string>"
        "<bool name=\"Anchored\">true</bool>"
        f"<Color3uint8 name=\"Color\">{cor}</Color3uint8>"
        f"<Vector3 name=\"size\"><X>8</X><Y>1</Y><Z>8</Z></Vector3>"
        f"<CoordinateFrame name=\"CFrame\">{_cf(x, y, z)}</CoordinateFrame>"
        "</Properties></Item>\n"
    )


def _script(ref: str, nome: str, fonte: str) -> str:
    return (
        f"<Item class=\"Script\" referent={quoteattr(ref)}>"
        "<Properties>"
        f"<string name=\"Name\">{escape(nome)}</string>"
        "<bool name=\"Disabled\">false</bool>"
        f"<ProtectedString name=\"Source\">{escape(fonte)}</ProtectedString>"
        "</Properties></Item>\n"
    )


def _camera(ref: str, x: float, y: float, z: float) -> str:
    return (
        f"<Item class=\"Camera\" referent={quoteattr(ref)}>"
        "<Properties>"
        "<string name=\"Name\">Camera</string>"
        f"<CoordinateFrame name=\"CFrame\">{_cf(x, y, z)}</CoordinateFrame>"
        "</Properties></Item>\n"
    )


def _fechar_workspace(ref: str, children: str, cam: str) -> str:
    return (
        f"<Item class=\"Workspace\" referent={quoteattr(ref)}>"
        "<Properties><string name=\"Name\">Workspace</string></Properties>"
        f"{cam}{children}</Item>\n"
    )


def _lighting(ref: str) -> str:
    return (
        f"<Item class=\"Lighting\" referent={quoteattr(ref)}>"
        "<Properties><string name=\"Name\">Lighting</string></Properties>"
        "</Item>\n"
    )


def _finalizar(children: str) -> str:
    return _CABECALHO + children + "</roblox>\n"


# ---------------------------------------------------------------- templates
_VERDE = 3309525325      # verde claro
_VERMELHO = 4285140029   # vermelho vivo
_CINZA = 1973697688      # cinza médio
_AZUL = 2667042018       # azul


def _obby(seed: int) -> str:
    r = random.Random(seed)
    ref = _Ref()
    partes = [_spawn(ref.novo(), "Spawn", 0, 0.5, 0, _VERDE)]
    partes.append(_part(ref.novo(), "Plataforma0", 0, 0.4, 12, 10, 1, 6, _CINZA))
    z = 20.0
    altura = 0.5
    n = 8 + r.randint(0, 4)
    for i in range(1, n + 1):
        altura += r.uniform(1.5, 3.0)
        x = r.uniform(-12.0, 12.0)
        eh_lava = (i % 3 == 0)
        sx = r.uniform(4.0, 7.0)
        if eh_lava:
            kill = _script(ref.novo(), "Mata", (
                "local p = script.Parent\n"
                "p.Touched:Connect(function(hit)\n"
                "\tlocal h = hit.Parent and hit.Parent:FindFirstChildOfClass(\"Humanoid\")\n"
                "\tif h then h.Health = 0 end\n"
                "end)\n"
            ))
            partes.append(_part(ref.novo(), f"Lava{i}", x, altura, z, sx, 1, 5, _VERMELHO, children=kill))
        else:
            partes.append(_part(ref.novo(), f"Plataforma{i}", x, altura, z, sx, 1, 5, _CINZA if i % 2 else _AZUL))
        z += r.uniform(8.0, 12.0)
    fim = altura + 1.0
    partes.append(_spawn(ref.novo(), "Fim", x, fim, z + 6, _VERDE))
    return _finalizar(_fechar_workspace(ref.novo(), "".join(partes), _camera(ref.novo(), 0, 12, -25)) + _lighting(ref.novo()))


def _arena(seed: int) -> str:
    r = random.Random(seed)
    ref = _Ref()
    partes = [_part(ref.novo(), "Piso", 0, -0.5, 0, 100, 1, 100, _CINZA)]
    partes.append(_spawn(ref.novo(), "SpawnAzul", -38, 0.5, 0, _AZUL))
    partes.append(_spawn(ref.novo(), "SpawnVermelho", 38, 0.5, 0, _VERMELHO))
    raio = 50.0
    n = 24
    for i in range(n):
        ang = 2 * math.pi * i / n
        x = raio * math.cos(ang)
        z = raio * math.sin(ang)
        h = r.uniform(6.0, 10.0)
        partes.append(_part(ref.novo(), f"Muro{i}", x, h / 2, z, 14, h, 3, _CINZA))
    for i in range(4):
        ang = r.uniform(0, 2 * math.pi)
        d = r.uniform(8.0, 28.0)
        partes.append(_part(ref.novo(), f"Obstaculo{i}", d * math.cos(ang), 2, d * math.sin(ang), r.uniform(3, 8), 4, r.uniform(3, 8), _AZUL))
    return _finalizar(_fechar_workspace(ref.novo(), "".join(partes), _camera(ref.novo(), 0, 60, -70)) + _lighting(ref.novo()))


def _base(seed: int) -> str:
    r = random.Random(seed)
    ref = _Ref()
    L = 40.0
    H = 12.0
    partes = [_part(ref.novo(), "PisoBase", 0, -0.5, 0, L + 4, 1, L + 4, _CINZA)]
    partes.append(_spawn(ref.novo(), "Spawn", 0, 0.5, 0, _VERDE))
    # 4 paredes com porta na frente (vão de 8 studs)
    frente_esq = -(L / 2) / 2 - 4
    for nome, x, z, sx, sz in (
        ("ParedeTras", 0, L / 2, L, 1),
        ("ParedeEsq", -L / 2, 0, 1, L),
        ("ParedeDir", L / 2, 0, 1, L),
        ("ParedeFrenteEsq", frente_esq, -L / 2, L / 2 - 8, 1),
        ("ParedeFrenteDir", -frente_esq, -L / 2, L / 2 - 8, 1),
    ):
        partes.append(_part(ref.novo(), nome, x, H / 2, z, sx, H, sz, _CINZA))
    partes.append(_part(ref.novo(), "Teto", 0, H + 0.5, 0, L + 4, 1, L + 4, _AZUL))
    # móveis simples
    partes.append(_part(ref.novo(), "Mesa", -8, 2, 8, 6, 3, 4, _VERDE))
    partes.append(_part(ref.novo(), "Bau", 8, 1.5, 8, 3, 3, 3, _VERMELHO))
    return _finalizar(_fechar_workspace(ref.novo(), "".join(partes), _camera(ref.novo(), 0, 30, -45)) + _lighting(ref.novo()))


_TEMPLATES = {
    "obby": _obby,
    "arena": _arena,
    "base": _base,
}

_DESCRICOES = {
    "obby": ("Obby completo: spawn, plataformas com alturas e posições variadas "
             "(seed-determinístico), blocos de lava com script que elimina ao tocar, "
             "e plataforma final de chegada."),
    "arena": "Arena PvP: piso amplo, muro circular, dois spawns por time e obstáculos centrais.",
    "base": "Base de jogador: piso, 4 paredes com porta na frente, teto e móveis básicos.",
}


def renderizar_ops(ops: list[dict], nome_camera_pos=(0, 40, -90)) -> str:
    """Renderiza um stream de operações do build_gen para .rbxlx nativo.

    Mesmo resultado do plugin-ponte, em arquivo: abre direto no Studio.
    """
    ref = _Ref()
    partes = []
    for op in ops:
        if op.get("op") != "part":
            continue
        cor = op.get("cor")
        cor_uint = None
        if cor is not None and len(cor) == 3:
            cor_uint = (int(cor[0]) << 16) | (int(cor[1]) << 8) | int(cor[2])
        partes.append(_part(
            ref.novo(),
            op.get("nome", "Part"),
            op["pos"][0], op["pos"][1], op["pos"][2],
            op["size"][0], op["size"][1], op["size"][2],
            cor=cor_uint,
            ancorado=bool(op.get("ancorado", True)),
        ))
    cx, cy, cz = nome_camera_pos
    return _finalizar(
        _fechar_workspace(ref.novo(), "".join(partes), _camera(ref.novo(), cx, cy, cz))
        + _lighting(ref.novo())
    )


def gerar_place(tipo: str, seed: int = 42) -> dict:
    """Gera um place .rbxlx nativo do Roblox Studio.

    Raises ValueError se o tipo for desconhecido.
    """
    t = (tipo or "").strip().lower()
    if t not in _TEMPLATES:
        raise ValueError(f"Place desconhecido. Opções: {', '.join(sorted(_TEMPLATES))}")
    xml = _TEMPLATES[t](seed)
    nome = f"arkher_{t}_seed{seed}.rbxlx"
    return {
        "descricao": (
            f"Place nativo do Roblox Studio gerado ({t}, seed {seed}).\n"
            f"{_DESCRICOES[t]}"
        ),
        "como_usar": (
            "Baixe o arquivo e abra direto no Roblox Studio (File → Open), "
            "ou arraste para o Studio. Tudo já vem construído — sem colar código."
        ),
        "arquivo": {"nome": nome, "conteudo": xml},
    }
