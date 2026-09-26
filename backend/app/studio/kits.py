"""Kits de produção da ARKHER v1 — o que um time médio de Roblox faria, já pronto.

Cada aba de game dev gera artefato real (Luau, .rbxlx, .rbxmx, PNG, JSON, .py).
Determinístico por seed. Sem modelo de terceiro.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from backend.app import config
from backend.app.studio import geral, jogo
from backend.app.tools import blender_gen, generators, rbxlx_gen

CATALOGO: list[dict] = [
    {
        "id": "places",
        "nome": {"pt-BR": "Places", "en": "Places"},
        "foco": "roblox",
        "hint": {
            "pt-BR": "Places .rbxlx prontos para abrir no Studio: obby, arena, base, tycoon, lobby RPG, pista.",
            "en": "Ready .rbxlx places: obby, arena, base, tycoon, RPG lobby, race.",
        },
        "receitas": [
            ("obby", "Obby / parkour"),
            ("arena", "Arena PvP"),
            ("base", "Base / HQ"),
            ("tycoon", "Tycoon (plot + dropper stub)"),
            ("lobby", "Lobby RPG"),
            ("pista", "Pista de corrida"),
            ("jogo", "Jogo inteiro (atelier, não template)"),
        ],
    },
    {
        "id": "models",
        "nome": {"pt-BR": "Models", "en": "Models"},
        "foco": "roblox",
        "hint": {
            "pt-BR": "Models .rbxmx: arma-tool, jipe, crate, dummy NPC, kit de prédio.",
            "en": ".rbxmx models: tool, jeep, crate, NPC dummy, building kit.",
        },
        "receitas": [
            ("sword", "Espada Tool"),
            ("jeep", "Jipe"),
            ("crate", "Crate / loot"),
            ("dummy", "Dummy NPC"),
            ("kit", "Kit de paredes"),
        ],
    },
    {
        "id": "luau",
        "nome": {"pt-BR": "Luau", "en": "Luau"},
        "foco": "roblox",
        "hint": {
            "pt-BR": "Sistemas de servidor: DataStore, remotes validados, inventário, combate, party.",
            "en": "Server systems: DataStore, validated remotes, inventory, combat, party.",
        },
        "receitas": [
            ("salvamento", "DataStore + session"),
            ("remotes", "Remotes + validação"),
            ("inventario", "Inventário"),
            ("combate", "Combate servidor"),
            ("party", "Party / grupo"),
        ],
    },
    {
        "id": "terrain",
        "nome": {"pt-BR": "Terreno", "en": "Terrain"},
        "foco": "roblox",
        "hint": {
            "pt-BR": "Receita de terreno do Studio + heightmap OBJ para Blender.",
            "en": "Studio terrain recipe + OBJ heightmap for Blender.",
        },
        "receitas": [
            ("montanha", "Montanha"),
            ("deserto", "Deserto"),
            ("planicie", "Planície"),
            ("neve", "Neve"),
            ("vulcao", "Vulcão"),
            ("obj", "Heightmap .obj"),
        ],
    },
    {
        "id": "animacao",
        "nome": {"pt-BR": "Animação", "en": "Animation"},
        "foco": "roblox",
        "hint": {
            "pt-BR": "Keyframes para o Animator + script Blender com action.",
            "en": "Animator keyframes + Blender action script.",
        },
        "receitas": [
            ("girar", "Girar"),
            ("flutuar", "Flutuar"),
            ("pulsar", "Pulsar"),
            ("vaivem", "Vai-e-vem"),
            ("blender", "Blender walk-cycle"),
        ],
    },
    {
        "id": "materiais",
        "nome": {"pt-BR": "Materiais", "en": "Materials"},
        "foco": "roblox",
        "hint": {
            "pt-BR": "Albedo PNG tileable + MaterialService Luau (sem asset roubado).",
            "en": "Tileable albedo PNG + MaterialService Luau.",
        },
        "receitas": [
            ("pedra", "Pedra"),
            ("grama", "Grama"),
            ("metal", "Metal"),
            ("madeira", "Madeira"),
            ("lava", "Lava"),
            ("areia", "Areia"),
        ],
    },
    {
        "id": "lighting",
        "nome": {"pt-BR": "Iluminação", "en": "Lighting"},
        "foco": "roblox",
        "hint": {
            "pt-BR": "Lighting + Atmosphere + ciclo dia/noite. Isso é o que separa amador de shipped.",
            "en": "Lighting + Atmosphere + day/night. What separates amateur from shipped.",
        },
        "receitas": [
            ("dia_noite", "Ciclo dia/noite"),
            ("sunset", "Pôr do sol"),
            ("horror", "Horror / noite"),
            ("neon", "Cidade neon"),
            ("indoor", "Interior"),
        ],
    },
    {
        "id": "ui",
        "nome": {"pt-BR": "UI / HUD", "en": "UI / HUD"},
        "foco": "roblox",
        "hint": {
            "pt-BR": "ScreenGui: vida, loja, inventário, diálogo, botões mobile.",
            "en": "ScreenGui: health, shop, inventory, dialog, mobile buttons.",
        },
        "receitas": [
            ("hud", "HUD vida/stamina"),
            ("loja", "Loja"),
            ("inventario_gui", "Inventário GUI"),
            ("dialogo", "Diálogo NPC"),
            ("mobile", "Botões mobile"),
        ],
    },
    {
        "id": "audio",
        "nome": {"pt-BR": "Áudio", "en": "Audio"},
        "foco": "roblox",
        "hint": {
            "pt-BR": "Mixer, SoundGroups, emissores 3D. Você cola os IDs oficiais da sua conta.",
            "en": "Mixer, SoundGroups, 3D emitters. Paste official IDs from your account.",
        },
        "receitas": [
            ("mixer", "Mixer / SoundGroups"),
            ("emitters", "Emissores 3D"),
            ("footsteps", "Footsteps por material"),
        ],
    },
    {
        "id": "fisica",
        "nome": {"pt-BR": "Física", "en": "Physics"},
        "foco": "roblox",
        "hint": {
            "pt-BR": "Constraints, veículo simples, canhão, ponte de corda — no servidor.",
            "en": "Constraints, simple vehicle, cannon, rope bridge — server-side.",
        },
        "receitas": [
            ("veiculo", "Chassis mola"),
            ("canhao", "Canhão"),
            ("corda", "Ponte de corda"),
            ("ragdoll", "Notas de ragdoll seguro"),
        ],
    },
    {
        "id": "netcode",
        "nome": {"pt-BR": "Netcode", "en": "Netcode"},
        "foco": "roblox",
        "hint": {
            "pt-BR": "Servidor autoritativo, cooldown, rate limit de remote, snapshot. Sem trapaça.",
            "en": "Authoritative server, cooldown, remote rate limit, snapshot. No cheats.",
        },
        "receitas": [
            ("validate", "Remote validado"),
            ("cooldown", "Cooldown + rate limit"),
            ("snapshot", "Snapshot de estado"),
            ("match", "Match stub"),
        ],
    },
    {
        "id": "vfx",
        "nome": {"pt-BR": "VFX", "en": "VFX"},
        "foco": "roblox",
        "hint": {
            "pt-BR": "ParticleEmitter, Trail, Beam — receitas prontas para copiar no efeito.",
            "en": "ParticleEmitter, Trail, Beam — ready recipes.",
        },
        "receitas": [
            ("explosao", "Explosão"),
            ("trail", "Trail de golpe"),
            ("fogo", "Fogo"),
            ("magia", "Magia"),
            ("chuva", "Chuva"),
        ],
    },
    {
        "id": "blender",
        "nome": {"pt-BR": "Blender", "en": "Blender"},
        "foco": "3d",
        "hint": {
            "pt-BR": "Scripts .py: personagem, cena, terreno, animação, textura 4K.",
            "en": ".py scripts: character, scene, terrain, animation, 4K texture.",
        },
        "receitas": [
            ("personagem", "Personagem"),
            ("cena", "Cena"),
            ("terreno", "Terreno"),
            ("animacao", "Animação"),
        ],
    },
    {
        "id": "design",
        "nome": {"pt-BR": "Design", "en": "Design"},
        "foco": "geral",
        "hint": {
            "pt-BR": "GDD, loop, economia e pilares — o briefing que as outras abas executam.",
            "en": "GDD, loop, economy and pillars — the brief the other tabs execute.",
        },
        "receitas": [
            ("gdd", "GDD (1 página)"),
            ("loop", "Loop nuclear"),
            ("economia", "Economia"),
            ("pilares", "Pilares"),
        ],
    },
    {
        "id": "pesquisa",
        "nome": {"pt-BR": "Pesquisa", "en": "Research"},
        "foco": "geral",
        "hint": {
            "pt-BR": "Fontes abertas (Wikipedia, Archive, docs). Atribuição na cara; sem rede, diz que falhou.",
            "en": "Open sources (Wikipedia, Archive, docs). Attribution on the page; offline = honest fail.",
        },
        "receitas": [
            ("brief", "Brief combinado"),
            ("wikipedia", "Wikipedia"),
            ("archive", "Internet Archive"),
            ("docs", "Docs oficiais"),
        ],
    },
    {
        "id": "codigo",
        "nome": {"pt-BR": "Código", "en": "Code"},
        "foco": "geral",
        "hint": {
            "pt-BR": "Python, shader, JSON do projeto, CI — o que não é Luau/Roblox.",
            "en": "Python, shader, project JSON, CI — everything that isn't Luau/Roblox.",
        },
        "receitas": [
            ("python", "Helper Python"),
            ("shader", "Shader toon"),
            ("json", "Schema do projeto"),
            ("ci", "CI GitHub"),
        ],
    },
    {
        "id": "pipeline",
        "nome": {"pt-BR": "Pipeline", "en": "Pipeline"},
        "foco": "geral",
        "hint": {
            "pt-BR": "Ship, export, QA e changelog — fechar o ciclo até publicar (com a sua confirmação).",
            "en": "Ship, export, QA and changelog — close the loop until publish (with your confirmation).",
        },
        "receitas": [
            ("ship", "Checklist de ship"),
            ("export", "Pacote de export"),
            ("qa", "Folha de QA"),
            ("changelog", "Notas de versão"),
        ],
    },
]


def _lua_file(nome: str, codigo: str, descricao: str) -> dict:
    return {
        "descricao": descricao,
        "arquivo": {"nome": nome, "conteudo": codigo},
        "como_usar": "Cole em ServerScriptService (ou StarterGui se for LocalScript). Revise IDs e números.",
    }


def _xml_model(nome: str, inner: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<roblox version="4">\n'
        f'<Item class="Model" referent="RBX1"><Properties>'
        f'<string name="Name">{escape(nome)}</string></Properties>\n'
        f"{inner}</Item>\n</roblox>\n"
    )


def _part(ref: str, nome: str, x: float, y: float, z: float, sx: float, sy: float, sz: float, cor: int) -> str:
    return (
        f'<Item class="Part" referent={quoteattr(ref)}><Properties>'
        f'<string name="Name">{escape(nome)}</string>'
        f'<bool name="Anchored">true</bool><bool name="CanCollide">true</bool>'
        f'<Color3uint8 name="Color">{cor}</Color3uint8>'
        f'<Vector3 name="size"><X>{sx:g}</X><Y>{sy:g}</Y><Z>{sz:g}</Z></Vector3>'
        f'<CoordinateFrame name="CFrame"><X>{x:g}</X><Y>{y:g}</Y><Z>{z:g}</Z>'
        "<R00>1</R00><R01>0</R01><R02>0</R02><R10>0</R10><R11>1</R11><R12>0</R12>"
        "<R20>0</R20><R21>0</R21><R22>1</R22></CoordinateFrame>"
        "</Properties></Item>\n"
    )


def _gerar_place(recipe: str, seed: int, prompt: str = "") -> dict:
    if recipe == "jogo":
        return jogo.completo(prompt or "atelier", seed)
    if recipe in ("obby", "arena", "base"):
        return rbxlx_gen.gerar_place(recipe, seed)
    tema = {
        "tycoon": "uma base com 2 casas, 1 torre e um mastro",
        "lobby": "uma vila com 4 casas e 3 arvores",
        "pista": "uma base com muralha e 2 veiculos",
    }.get(recipe, "uma base")
    from backend.app.tools import build_gen

    ops = build_gen.compor(tema, seed)
    xml = rbxlx_gen.renderizar_ops(ops)
    return {
        "descricao": f"Place '{recipe}' (seed {seed}) — {len(ops)} peças, spawn/luz inclusos.",
        "como_usar": "Baixe o .rbxlx e abra no Roblox Studio, ou mande ao Workspace.",
        "arquivo": {"nome": f"arkher_{recipe}_seed{seed}.rbxlx", "conteudo": xml},
    }


def _gerar_model(recipe: str, seed: int) -> dict:
    if recipe == "sword":
        inner = _part("RBX2", "Handle", 0, 1, 0, 0.4, 4, 0.4, 0xC0C0C0) + _part(
            "RBX3", "Guarda", 0, 3, 0, 1.6, 0.3, 0.3, 0xC9A227
        )
        nome = "ArkherSword"
    elif recipe == "jeep":
        inner = (
            _part("RBX2", "Chassi", 0, 1.2, 0, 8, 1.2, 4.5, 0x3A3A3A)
            + _part("RBX3", "Cabine", -1.2, 2.4, 0, 4, 1.6, 4.2, 0x2E5A3C)
            + _part("RBX4", "RodaFL", 3, 0.7, 2, 1.2, 1.2, 0.6, 0x1A1A1A)
            + _part("RBX5", "RodaFR", 3, 0.7, -2, 1.2, 1.2, 0.6, 0x1A1A1A)
            + _part("RBX6", "RodaBL", -3, 0.7, 2, 1.2, 1.2, 0.6, 0x1A1A1A)
            + _part("RBX7", "RodaBR", -3, 0.7, -2, 1.2, 1.2, 0.6, 0x1A1A1A)
        )
        nome = "ArkherJeep"
    elif recipe == "dummy":
        inner = (
            _part("RBX2", "HumanoidRootPart", 0, 3, 0, 2, 2, 1, 0xAAAAAA)
            + _part("RBX3", "Head", 0, 5, 0, 2, 1, 1, 0xF5CBA7)
            + _part("RBX4", "Torso", 0, 3.5, 0, 2, 2, 1, 0x2E86AB)
        )
        nome = "ArkherDummy"
    elif recipe == "kit":
        inner = "".join(
            _part(f"RBX{i+2}", f"Parede{i}", i * 4.0, 4, 0, 4, 8, 0.4, 0x8D6E63) for i in range(6)
        )
        nome = "ArkherWallKit"
    else:
        inner = _part("RBX2", "Crate", 0, 1, 0, 3, 3, 3, 0xA67C52)
        nome = "ArkherCrate"
    xml = _xml_model(nome, inner)
    return {
        "descricao": f"Model {nome} (seed {seed}) em .rbxmx nativo.",
        "como_usar": "Arraste o .rbxmx para o Studio ou Importe. Transforme a espada em Tool com Handle.",
        "arquivo": {"nome": f"arkher_{recipe}_seed{seed}.rbxmx", "conteudo": xml},
    }


_LUAU = {
    "salvamento": generators.gerar_roblox,
    "remotes": lambda _t: _lua_file(
        "ArkherRemotes.lua",
        '''-- ARKHER: remotes com validação no servidor (autoritativo)
local RS = game:GetService("ReplicatedStorage")
local pasta = RS:FindFirstChild("Arkher") or Instance.new("Folder", RS)
pasta.Name = "Arkher"
local ev = pasta:FindFirstChild("Acao") or Instance.new("RemoteEvent", pasta)
ev.Name = "Acao"

local RATE = {} -- userId -> {t, n}
local MAX_POR_S = 8

local function rateOk(player)
	local now = os.clock()
	local s = RATE[player.UserId] or {t = now, n = 0}
	if now - s.t > 1 then s = {t = now, n = 0} end
	s.n += 1
	RATE[player.UserId] = s
	return s.n <= MAX_POR_S
end

ev.OnServerEvent:Connect(function(player, acao, payload)
	if typeof(acao) ~= "string" or #acao > 32 then return end
	if not rateOk(player) then return end
	if acao == "pegar" then
		local dist = player:DistanceFromCharacter(payload and payload.pos or Vector3.zero)
		if typeof(dist) == "number" and dist > 12 then return end
		-- aplique o efeito no servidor, nunca confie no cliente
	end
end)
''',
        "RemoteEvent com rate-limit e validação. Cliente só pede; servidor decide.",
    ),
    "inventario": lambda _t: _lua_file(
        "ArkherInventario.lua",
        '''-- ARKHER: inventário servidor (tabela + replica via remote)
local Players = game:GetService("Players")
local RS = game:GetService("ReplicatedStorage")
local ev = RS:WaitForChild("Arkher"):WaitForChild("Acao")
local INV = {} -- userId -> {id=qty}

local function replica(player)
	ev:FireClient(player, "inv", INV[player.UserId] or {})
end

Players.PlayerAdded:Connect(function(p) INV[p.UserId] = INV[p.UserId] or {} replica(p) end)
Players.PlayerRemoving:Connect(function(p) INV[p.UserId] = nil end)

local function add(player, id, n)
	if typeof(id) ~= "string" or #id > 24 then return end
	n = math.clamp(tonumber(n) or 0, 1, 99)
	local bag = INV[player.UserId]
	if not bag then return end
	bag[id] = math.min(99, (bag[id] or 0) + n)
	replica(player)
end

return { add = add, replica = replica }
''',
        "Inventário só no servidor, replica para o HUD. Combine com DataStore.",
    ),
    "combate": lambda _t: _lua_file(
        "ArkherCombate.lua",
        '''-- ARKHER: hitbox servidor, cooldown, sem god-client
local Players = game:GetService("Players")
local CD = {}
local DANO = 12
local ALCANCE = 8

local function pode(p)
	local t = os.clock()
	if (CD[p.UserId] or 0) > t then return false end
	CD[p.UserId] = t + 0.45
	return true
end

local function golpear(player)
	if not pode(player) then return end
	local char = player.Character
	local hrp = char and char:FindFirstChild("HumanoidRootPart")
	if not hrp then return end
	for _, pl in ipairs(Players:GetPlayers()) do
		if pl ~= player and pl.Character then
			local alvo = pl.Character:FindFirstChild("HumanoidRootPart")
			local hum = pl.Character:FindFirstChildOfClass("Humanoid")
			if alvo and hum and (alvo.Position - hrp.Position).Magnitude <= ALCANCE then
				hum:TakeDamage(DANO)
			end
		end
	end
end

return { golpear = golpear }
''',
        "Golpe autoritativo. Cliente só dispara o pedido; dano é no Humanoid do servidor.",
    ),
    "party": lambda _t: _lua_file(
        "ArkherParty.lua",
        '''-- ARKHER: party simples (líder + membros, máx 4)
local Parties = {} -- leaderUserId -> {members={userId...}}
local MAX = 4

local function partyDe(userId)
	for lid, p in pairs(Parties) do
		if lid == userId then return lid, p end
		for _, m in ipairs(p.members) do if m == userId then return lid, p end end
	end
end

local function convite(lider, alvo)
	if lider.UserId == alvo.UserId then return end
	local lid, p = partyDe(lider.UserId)
	if not p then p = {members = {lider.UserId}} Parties[lider.UserId] = p lid = lider.UserId end
	if lid ~= lider.UserId then return end
	if #p.members >= MAX then return end
	if partyDe(alvo.UserId) then return end
	table.insert(p.members, alvo.UserId)
end

return { convite = convite, partyDe = partyDe }
''',
        "Party máx 4. Use com teleport de grupo e split de loot.",
    ),
}


def _gerar_luau(recipe: str) -> dict:
    if recipe == "salvamento":
        return generators.gerar_roblox("salvamento")
    fn = _LUAU.get(recipe)
    if not fn:
        raise ValueError("receita luau desconhecida")
    return fn(recipe)


def _gerar_lighting(recipe: str) -> dict:
    presets = {
        "dia_noite": ("ciclo", 14, 0.35, 0.012),
        "sunset": ("pôr do sol", 17.4, 0.55, 0.03),
        "horror": ("horror", 0.4, 0.85, 0.08),
        "neon": ("neon", 20.2, 0.4, 0.02),
        "indoor": ("interior", 12, 0.2, 0.005),
    }
    nome, clock, fog, amb = presets.get(recipe, presets["dia_noite"])
    codigo = f'''-- ARKHER Lighting: {nome}
local L = game:GetService("Lighting")
L.ClockTime = {clock}
L.Brightness = 2
L.Ambient = Color3.fromRGB({int(amb*255)}, {int(amb*255)}, {int(amb*40+20)})
L.OutdoorAmbient = Color3.fromRGB(80, 90, 110)
L.FogEnd = {int(400 + fog * 800)}
L.FogColor = Color3.fromRGB(20, 24, 40)
local at = L:FindFirstChildOfClass("Atmosphere") or Instance.new("Atmosphere", L)
at.Density = {fog}
at.Offset = 0.1
at.Color = Color3.fromRGB(90, 110, 140)
'''
    if recipe == "dia_noite":
        codigo += "\n" + generators.gerar_roblox("dia_noite")["codigo"]
    return _lua_file(f"ArkherLighting_{recipe}.lua", codigo, f"Iluminação '{nome}' — Atmosphere + Lighting.")


def _gerar_ui(recipe: str) -> dict:
    codigo = {
        "hud": '''-- LocalScript em StarterGui
local pg = game.Players.LocalPlayer:WaitForChild("PlayerGui")
local gui = Instance.new("ScreenGui", pg)
gui.Name = "ArkherHUD"
gui.ResetOnSpawn = false
local bar = Instance.new("Frame", gui)
bar.Size = UDim2.new(0.28, 0, 0.03, 0)
bar.Position = UDim2.new(0.02, 0, 0.92, 0)
bar.BackgroundColor3 = Color3.fromRGB(20, 20, 20)
local fill = Instance.new("Frame", bar)
fill.Name = "Fill"
fill.Size = UDim2.new(1, 0, 1, 0)
fill.BackgroundColor3 = Color3.fromRGB(40, 200, 90)
local hum
local function bind(c)
	hum = c and c:FindFirstChildOfClass("Humanoid")
end
bind(game.Players.LocalPlayer.Character)
game.Players.LocalPlayer.CharacterAdded:Connect(bind)
game:GetService("RunService").RenderStepped:Connect(function()
	if hum then fill.Size = UDim2.new(hum.Health / math.max(hum.MaxHealth, 1), 0, 1, 0) end
end)
''',
        "loja": '''-- LocalScript: loja modal. Compras vão por RemoteEvent (servidor confirma).
local RS = game:GetService("ReplicatedStorage")
local ev = RS:WaitForChild("Arkher"):WaitForChild("Acao")
local pg = game.Players.LocalPlayer:WaitForChild("PlayerGui")
local gui = Instance.new("ScreenGui", pg)
gui.Name = "ArkherLoja"
local frame = Instance.new("Frame", gui)
frame.Size = UDim2.fromScale(0.4, 0.5)
frame.Position = UDim2.fromScale(0.3, 0.25)
frame.BackgroundColor3 = Color3.fromRGB(18, 22, 28)
for i, item in ipairs({"Espada", "Pocao", "Mochila"}) do
	local b = Instance.new("TextButton", frame)
	b.Size = UDim2.new(0.9, 0, 0.18, 0)
	b.Position = UDim2.new(0.05, 0, 0.08 + (i-1)*0.22, 0)
	b.Text = "Comprar "..item
	b.MouseButton1Click:Connect(function() ev:FireServer("comprar", {id = item}) end)
end
''',
        "inventario_gui": '''-- LocalScript: grade 5x4 lendo replica "inv"
local ev = game:GetService("ReplicatedStorage"):WaitForChild("Arkher"):WaitForChild("Acao")
local pg = game.Players.LocalPlayer:WaitForChild("PlayerGui")
local gui = Instance.new("ScreenGui", pg)
gui.Name = "ArkherInv"
local grid = Instance.new("Frame", gui)
grid.Size = UDim2.fromScale(0.36, 0.4)
grid.Position = UDim2.fromScale(0.32, 0.3)
local ui = Instance.new("UIGridLayout", grid)
ui.CellSize = UDim2.new(0.18, 0, 0.22, 0)
ev.OnClientEvent:Connect(function(kind, bag)
	if kind ~= "inv" then return end
	grid:ClearAllChildren()
	Instance.new("UIGridLayout", grid).CellSize = UDim2.new(0.18, 0, 0.22, 0)
	for id, n in pairs(bag) do
		local t = Instance.new("TextLabel", grid)
		t.Text = id.." x"..n
	end
end)
''',
        "dialogo": '''-- LocalScript: caixa de diálogo
local pg = game.Players.LocalPlayer:WaitForChild("PlayerGui")
local gui = Instance.new("ScreenGui", pg)
gui.Name = "ArkherDialogo"
local box = Instance.new("TextLabel", gui)
box.Size = UDim2.new(0.6, 0, 0.16, 0)
box.Position = UDim2.new(0.2, 0, 0.78, 0)
box.BackgroundColor3 = Color3.fromRGB(10, 10, 14)
box.TextColor3 = Color3.new(1,1,1)
box.TextWrapped = true
box.Visible = false
local function falar(texto)
	box.Visible = true
	box.Text = texto
end
return { falar = falar }
''',
        "mobile": '''-- LocalScript: botões jump/golpe para touch
local pg = game.Players.LocalPlayer:WaitForChild("PlayerGui")
local gui = Instance.new("ScreenGui", pg)
gui.Name = "ArkherMobile"
local function botao(nome, pos, cb)
	local b = Instance.new("TextButton", gui)
	b.Size = UDim2.fromOffset(72, 72)
	b.Position = pos
	b.Text = nome
	b.BackgroundColor3 = Color3.fromRGB(30, 30, 30)
	b.MouseButton1Click:Connect(cb)
end
botao("Golpe", UDim2.new(0.82, 0, 0.72, 0), function()
	game:GetService("ReplicatedStorage"):WaitForChild("Arkher"):WaitForChild("Acao"):FireServer("golpe")
end)
''',
    }[recipe]
    return _lua_file(f"ArkherUI_{recipe}.lua", codigo, f"UI '{recipe}' — LocalScript, dados vêm do servidor.")


def _gerar_audio(recipe: str) -> dict:
    codigo = {
        "mixer": '''-- SoundGroups: Sfx, Musica, Voz. Volume master no Settings.
local SoundService = game:GetService("SoundService")
local function grp(nome, vol)
	local g = SoundService:FindFirstChild(nome) or Instance.new("SoundGroup", SoundService)
	g.Name = nome
	g.Volume = vol
	return g
end
grp("Sfx", 0.8); grp("Musica", 0.45); grp("Voz", 1)
''',
        "emitters": '''-- Cole em um Part: emissor 3D (RollOff)
local s = Instance.new("Sound")
s.SoundGroup = game:GetService("SoundService"):FindFirstChild("Sfx")
s.RollOffMode = Enum.RollOffMode.InverseTapered
s.RollOffMinDistance = 8
s.RollOffMaxDistance = 80
s.Looped = true
-- s.SoundId = "rbxassetid://SEU_ID_LICENCIADO"
s.Parent = script.Parent
s:Play()
''',
        "footsteps": '''-- Footsteps por material (raycast no chão). IDs: os seus.
local char = game.Players.LocalPlayer.Character or game.Players.LocalPlayer.CharacterAdded:Wait()
local hrp = char:WaitForChild("HumanoidRootPart")
local hum = char:WaitForChild("Humanoid")
local MAP = { [Enum.Material.Grass] = "", [Enum.Material.Concrete] = "", [Enum.Material.Wood] = "" }
hum.Running:Connect(function(speed)
	if speed < 8 then return end
	local params = RaycastParams.new()
	params.FilterDescendantsInstances = {char}
	local hit = workspace:Raycast(hrp.Position, Vector3.new(0, -4, 0), params)
	if hit and MAP[hit.Material] then
		-- toque o som do material (ID seu)
	end
end)
''',
    }[recipe]
    return _lua_file(f"ArkherAudio_{recipe}.lua", codigo, "Áudio: cole IDs da sua conta. Nada de asset pirata.")


def _gerar_fisica(recipe: str) -> dict:
    codigo = {
        "veiculo": "-- Chassis: 4 CylinderCollider + SpringConstraint no chassi. Monte no Studio; torque no servidor.\n-- Evite VehicleSeat só no cliente: sete MaxSpeed no servidor.",
        "canhao": '''local barrel = script.Parent
local ev = game:GetService("ReplicatedStorage"):WaitForChild("Arkher"):WaitForChild("Acao")
ev.OnServerEvent:Connect(function(player, acao)
	if acao ~= "fogo" then return end
	if player:DistanceFromCharacter(barrel.Position) > 16 then return end
	local b = Instance.new("Part")
	b.Shape = Enum.PartType.Ball
	b.Size = Vector3.new(1,1,1)
	b.CFrame = barrel.CFrame * CFrame.new(0,0,-4)
	b.AssemblyLinearVelocity = barrel.CFrame.LookVector * 120
	b.Parent = workspace
	game:GetService("Debris"):AddItem(b, 4)
end)
''',
        "corda": "-- RopeConstraint entre 8 Parts ancoradas nas pontas. Thickness 0.2, WinchEnabled false.",
        "ragdoll": "-- Ragdoll: substitua Motor6D por BallSocket no Humanoid.Died, só no personagem do player. Sem replicar hitbox de terceiro.",
    }[recipe]
    return _lua_file(f"ArkherFisica_{recipe}.lua", codigo, f"Física '{recipe}' — constraints no servidor.")


def _gerar_netcode(recipe: str) -> dict:
    if recipe == "validate":
        return _LUAU["remotes"]("remotes")
    codigo = {
        "cooldown": '''local CD = {}
return function(player, key, sec)
	sec = sec or 1
	local now = os.clock()
	local bag = CD[player.UserId] or {}
	if (bag[key] or 0) > now then return false end
	bag[key] = now + sec
	CD[player.UserId] = bag
	return true
end
''',
        "snapshot": '''-- Snapshot 10 Hz: só o que mudou (delta). Servidor é a verdade.
local last = {}
game:GetService("RunService").Heartbeat:Connect(function()
	-- monte {pos, hp} por player e FireAllClients a cada 0.1s
end)
''',
        "match": '''local FILA = {}
local function tick()
	if #FILA >= 2 then
		local a, b = table.remove(FILA, 1), table.remove(FILA, 1)
		-- teleport a,b para arena reservada
	end
end
return { entra = function(p) table.insert(FILA, p) tick() end }
''',
    }[recipe]
    return _lua_file(f"ArkherNet_{recipe}.lua", codigo, f"Netcode '{recipe}' — servidor autoritativo.")


def _gerar_vfx(recipe: str) -> dict:
    codigo = f'''-- ARKHER VFX: {recipe}
local att = Instance.new("Attachment")
att.Parent = script.Parent
local p = Instance.new("ParticleEmitter", att)
p.Rate = 40
p.Lifetime = NumberRange.new(0.3, 0.8)
p.Speed = NumberRange.new(4, 12)
p.SpreadAngle = Vector2.new(30, 30)
p.Size = NumberSequence.new(0.6, 0)
p.LightEmission = 0.4
-- p.Texture = "rbxassetid://SEU_ID"
if "{recipe}" == "trail" then
	local t = Instance.new("Trail", script.Parent)
	t.Lifetime = 0.25
	t.Attachment0 = att
	local a2 = Instance.new("Attachment", script.Parent)
	t.Attachment1 = a2
end
'''
    return _lua_file(f"ArkherVfx_{recipe}.lua", codigo, f"VFX '{recipe}'. Texture: ID seu.")


def gerar(tab: str, recipe: str, seed: int = 42, prompt: str = "") -> dict:
    tab, recipe = (tab or "").strip().lower(), (recipe or "").strip().lower()
    seed = int(seed)
    validar(tab, recipe)
    if tab == "places":
        res = _gerar_place(recipe, seed, prompt)
    elif tab == "models":
        res = _gerar_model(recipe, seed)
    elif tab == "luau":
        res = _gerar_luau(recipe)
    elif tab == "terrain":
        res = generators.gerar_terreno(seed) if recipe == "obj" else generators.gerar_terreno_studio(recipe, str(seed))
    elif tab == "animacao":
        if recipe == "blender":
            script = blender_gen.gerar_script("animacao", seed)
            res = {"descricao": "Animação Blender (keyframes + textura).", "arquivo": {"nome": f"animacao_seed{seed}_arkher.py", "conteudo": script}}
        else:
            res = generators.gerar_animacao(recipe, seed, 2.0)
    elif tab == "materiais":
        res = generators.gerar_textura(recipe, seed)
    elif tab == "lighting":
        res = _gerar_lighting(recipe)
    elif tab == "ui":
        res = _gerar_ui(recipe)
    elif tab == "audio":
        res = _gerar_audio(recipe)
    elif tab == "fisica":
        res = _gerar_fisica(recipe)
    elif tab == "netcode":
        res = _gerar_netcode(recipe)
    elif tab == "vfx":
        res = _gerar_vfx(recipe)
    elif tab == "blender":
        script = blender_gen.gerar_script(recipe, seed)
        res = {
            "descricao": f"Script Blender '{recipe}' seed {seed}.",
            "arquivo": {"nome": f"{recipe}_seed{seed}_arkher.py", "conteudo": script},
            "como_usar": "Rode no Blender ou mande ao Workspace.",
        }
    elif tab == "design":
        res = geral.gerar_design(recipe, prompt, seed)
    elif tab == "pesquisa":
        res = geral.gerar_pesquisa(recipe, prompt)
    elif tab == "codigo":
        res = geral.gerar_codigo(recipe, prompt, seed)
    elif tab == "pipeline":
        res = geral.gerar_pipeline(recipe, prompt, seed)
    else:
        raise ValueError(f"aba/receita desconhecida: {tab}/{recipe}")
    return _com_arquivo(tab, recipe, seed, res)


def _com_arquivo(tab: str, recipe: str, seed: int, res: dict) -> dict:
    if res.get("arquivo"):
        return res
    if res.get("codigo"):
        res["arquivo"] = {"nome": f"arkher_{tab}_{recipe}.lua", "conteudo": res["codigo"]}
        return res
    res["arquivo"] = {
        "nome": f"arkher_{tab}_{recipe}_seed{seed}.json",
        "conteudo": json.dumps(res, ensure_ascii=False, indent=2)[:120000],
    }
    return res


def listar_vault() -> list[dict]:
    root = config.DATA_DIR / "generated"
    out: list[dict] = []
    if not root.exists():
        return out
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix.lower() in {".rbxlx", ".rbxmx", ".lua", ".py", ".obj", ".png", ".json", ".txt"}:
            out.append({
                "path": str(p),
                "nome": p.name,
                "pasta": p.parent.name,
                "bytes": p.stat().st_size,
                "tipo": p.suffix.lower()[1:],
            })
    return out[:200]


def validar(tab: str, recipe: str) -> None:
    for c in CATALOGO:
        if c["id"] == tab:
            ids = {r[0] for r in c["receitas"]}
            if recipe not in ids:
                raise ValueError("receita inválida para " + tab)
            return
    raise ValueError("aba desconhecida")
