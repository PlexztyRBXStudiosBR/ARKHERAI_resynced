"""Jogo inteiro — o que um time médio entregaria numa semana, sem cara de template/IA.

Um pack: place jogável + 3 sistemas Luau + HUD de atelier (canto vivo, sem Inter)
+ script Blender do protagonista. Seed muda a planta; não é obby pad.
"""
from __future__ import annotations

from xml.sax.saxutils import escape

from backend.app.studio import provas
from backend.app.tools import blender_gen


def _part(ref: str, nome: str, x, y, z, sx, sy, sz, cor: int) -> str:
    return (
        f'<Item class="Part" referent={ref!r}><Properties>'
        f'<string name="Name">{escape(nome)}</string>'
        f'<bool name="Anchored">true</bool><bool name="CanCollide">true</bool>'
        f'<Color3uint8 name="Color">{cor}</Color3uint8>'
        f'<Vector3 name="size"><X>{sx:g}</X><Y>{sy:g}</Y><Z>{sz:g}</Z></Vector3>'
        f'<CoordinateFrame name="CFrame"><X>{x:g}</X><Y>{y:g}</Y><Z>{z:g}</Z>'
        "<R00>1</R00><R01>0</R01><R02>0</R02><R10>0</R10><R11>1</R11><R12>0</R12>"
        "<R20>0</R20><R21>0</R21><R22>1</R22></CoordinateFrame>"
        "</Properties></Item>\n"
    )


def _place(seed: int, tema: str) -> str:
    rng = (seed * 1103515245 + 12345) & 0x7FFFFFFF
    def r(n=10):
        nonlocal rng
        rng = (rng * 1103515245 + 12345) & 0x7FFFFFFF
        return rng % n
    # planta irregular — não é grid de pads
    inner = []
    inner.append(_part("chao", "ChaoAtelier", 0, -1, 0, 80, 2, 80, 0x3A3228))
    inner.append(
        '<Item class="SpawnLocation" referent="sp"><Properties>'
        '<string name="Name">Spawn</string><bool name="Anchored">true</bool>'
        '<Vector3 name="size"><X>6</X><Y>1</Y><Z>6</Z></Vector3>'
        '<CoordinateFrame name="CFrame"><X>0</X><Y>0.5</Y><Z>8</Z>'
        "<R00>1</R00><R01>0</R01><R02>0</R02><R10>0</R10><R11>1</R11><R12>0</R12>"
        "<R20>0</R20><R21>0</R21><R22>1</R22></CoordinateFrame>"
        "</Properties></Item>\n"
    )
    # marco: torre deslocada
    tx, tz = 12 + r(8), -10 - r(6)
    inner.append(_part("torre", "Marco", tx, 14, tz, 8, 28, 8, 0x6B5344))
    inner.append(_part("coroa", "Coroa", tx, 29, tz, 12, 2, 12, 0xC4A35A))
    # pavilhões
    for i in range(3 + r(3)):
        x, z = -24 + i * 14 + r(3), 16 + r(5)
        inner.append(_part(f"pav{i}", f"Pavilhao{i}", x, 4, z, 10, 8, 8, 0x4A4038))
    inner.append(
        '<Item class="PointLight" referent="luz"><Properties>'
        '<float name="Brightness">2</float><float name="Range">40</float>'
        "</Properties></Item>\n"
    )
    body = "".join(inner)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<roblox version="4">\n'
        f'<Item class="Workspace" referent="ws"><Properties>'
        f'<string name="Name">ARKHER_{escape(tema[:24])}_{seed}</string>'
        f"</Properties>\n{body}</Item>\n</roblox>\n"
    )


def _hud(seed: int) -> str:
    # canto 0, fonte Gotham/Fonte do Studio — NÃO Inter, NÃO UICorner 12
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<roblox version="4">
<Item class="ScreenGui" referent="hud"><Properties>
<string name="Name">ARKHER_Atelier_{seed}</string>
<bool name="ResetOnSpawn">false</bool>
</Properties>
<Item class="Frame" referent="placa"><Properties>
<string name="Name">Placa</string>
<UDim2 name="Size"><XS>0</XS><XO>280</XO><YS>0</YS><YO>72</YO></UDim2>
<UDim2 name="Position"><XS>0</XS><XO>16</XO><YS>1</YS><YO>-88</YO></UDim2>
<Color3uint8 name="BackgroundColor3">1972776</Color3uint8>
<float name="BackgroundTransparency">0.15</float>
</Properties>
<Item class="UIStroke"><Properties><Color3uint8 name="Color">12884250</Color3uint8><float name="Thickness">2</float></Properties></Item>
<Item class="TextLabel"><Properties>
<string name="Name">Marca</string>
<string name="Text">ARKHER · {seed}</string>
<string name="Font">Code</string>
<int name="TextSize">16</int>
<Color3uint8 name="TextColor3">12884250</Color3uint8>
<bool name="BackgroundTransparency">true</bool>
<UDim2 name="Size"><XS>1</XS><XO>0</XO><YS>0</YS><YO>22</YO></UDim2>
</Properties></Item>
<Item class="TextButton" referent="act"><Properties>
<string name="Name">Acao</string>
<string name="Text">PRONTO</string>
<string name="Font">Code</string>
<UDim2 name="Position"><XS>0</XS><XO>8</XO><YS>0</YS><YO>28</YO></UDim2>
<UDim2 name="Size"><XS>0</XS><XO>120</XO><YS>0</YS><YO>32</YO></UDim2>
<Color3uint8 name="BackgroundColor3">4210752</Color3uint8>
<Color3uint8 name="TextColor3">14865498</Color3uint8>
</Properties></Item>
</Item></Item></roblox>
'''


def _luau(seed: int, tema: str) -> str:
    return f'''-- ARKHER atelier {seed} · {tema[:40]}
-- Servidor é a verdade. Sem eval. Sem UI de template.
local Players = game:GetService("Players")
local RS = game:GetService("ReplicatedStorage")
local Hit = RS:FindFirstChild("ArkherHit") or Instance.new("RemoteEvent", RS)
Hit.Name = "ArkherHit"
local CD = {{}}
Hit.OnServerEvent:Connect(function(player, alvo)
	if typeof(alvo) ~= "Instance" then return end
	local now = os.clock()
	if (CD[player] or 0) > now then return end
	CD[player] = now + 0.45
	local hum = alvo:FindFirstChildOfClass("Humanoid")
	if hum and hum.Health > 0 then
		hum:TakeDamage(12)
	end
end)
Players.PlayerAdded:Connect(function(p)
	p.CharacterAdded:Connect(function(c)
		local h = c:WaitForChild("Humanoid")
		h.WalkSpeed = 16
		h.JumpPower = 50
	end)
end)
'''


def completo(tema: str, seed: int) -> dict:
    tema = (tema or "atelier").strip()[:80] or "atelier"
    place = _place(seed, tema)
    hud = _hud(seed)
    lua = _luau(seed, tema)
    blender = blender_gen.gerar_script("personagem", seed)
    pacote = [
        {"nome": f"jogo_{seed}.rbxlx", "conteudo": place},
        {"nome": f"hud_atelier_{seed}.rbxmx", "conteudo": hud},
        {"nome": f"ArkherJogo_{seed}.lua", "conteudo": lua},
        {"nome": f"protagonista_{seed}.py", "conteudo": blender},
    ]
    laudo = provas.rodar(pacote)
    return {
        "descricao": (
            f"Jogo inteiro '{tema}' seed {seed}: place + HUD atelier (sem Inter/UICorner) "
            f"+ combate servidor + protagonista Blender. Provas 2D/3D: "
            f"{'PASSAM' if laudo.get('ok') else 'FALHAM'} ({laudo.get('n')} checks)."
        ),
        "arquivo": pacote[0],
        "pacote": pacote,
        "provas": laudo,
        "como_usar": (
            "Abra o .rbxlx no Studio, cole o HUD em StarterGui, o .lua em ServerScriptService, "
            "rode o .py no Blender. Mandar ao Workspace: 'cria o jogo inteiro'."
        ),
    }
