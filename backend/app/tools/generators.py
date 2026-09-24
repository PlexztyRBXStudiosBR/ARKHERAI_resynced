"""Geradores game dev do ARKHER — ferramentas determinísticas do próprio projeto.

Produzem código e assets reais para o usuário usar nas ferramentas DELE
(Roblox Studio, Blender/engines que importam OBJ), com revisão humana.
Nenhuma máquina é controlada remotamente.
"""
from __future__ import annotations

import math
import random
import unicodedata


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", (t or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))


# --------------------------------------------------------------- Roblox/Luau
def _leaderstats() -> str:
    return '''-- ARKHER: leaderstats com moedas
-- Cole em ServerScriptService
local Players = game:GetService("Players")

Players.PlayerAdded:Connect(function(player)
	local stats = Instance.new("Folder")
	stats.Name = "leaderstats"

	local moedas = Instance.new("IntValue")
	moedas.Name = "Moedas"
	moedas.Value = 0
	moedas.Parent = stats

	stats.Parent = player
end)

game:GetService("ReplicatedStorage"):WaitForChild("MoedaColetada", 5)
'''


def _salvamento() -> str:
    return '''-- ARKHER: salvamento com DataStore
-- Cole em ServerScriptService
local DataStoreService = game:GetService("DataStoreService")
local Players = game:GetService("Players")
local store = DataStoreService:GetDataStore("arkher_saves_v1")

local function chave(player)
	return "u_" .. player.UserId
end

Players.PlayerAdded:Connect(function(player)
	local stats = Instance.new("Folder")
	stats.Name = "leaderstats"
	local moedas = Instance.new("IntValue")
	moedas.Name = "Moedas"
	moedas.Parent = stats
	stats.Parent = player

	local ok, dado = pcall(function()
		return store:GetAsync(chave(player))
	end)
	if ok and type(dado) == "table" then
		moedas.Value = dado.moedas or 0
	end
end)

Players.PlayerRemoving:Connect(function(player)
	local stats = player:FindFirstChild("leaderstats")
	if not stats then return end
	pcall(function()
		store:SetAsync(chave(player), { moedas = stats.Moedas.Value })
	end)
end)

game:BindToClose(function()
	for _, player in ipairs(Players:GetPlayers()) do
		local stats = player:FindFirstChild("leaderstats")
		if stats then
			pcall(function()
				store:SetAsync(chave(player), { moedas = stats.Moedas.Value })
			end)
		end
	end
end)
'''


def _teleporte() -> str:
    return '''-- ARKHER: pads de teleporte
-- Cole em ServerScriptService e crie uma pasta "Teleportes" no Workspace
-- com Parts nomeadas "A", "B", "C"...
local pasta = workspace:WaitForChild("Teleportes")
local destino = {}

for _, part in ipairs(pasta:GetChildren()) do
	if part:IsA("BasePart") then
		destino[part.Name] = part
	end
end

for nome, part in pairs(destino) do
	part.Touched:Connect(function(hit)
		local char = hit:FindFirstAncestorOfClass("Model")
		local humanoid = char and char:FindFirstChildOfClass("Humanoid")
		if not humanoid then return end
		local prox = nome:sub(1, 1):upper() == nome:sub(1, 1) and nome:lower() or nome
		local alvo = destino[prox .. "_alvo"] or destino[nome .. "_alvo"]
		if alvo then
			char:PivotTo(alvo.CFrame + Vector3.new(0, 3, 0))
		end
	end)
end
'''


def _dia_noite() -> str:
    return '''-- ARKHER: ciclo de dia e noite
-- Cole em ServerScriptService
local Lighting = game:GetService("Lighting")

local MINUTO_DE_JOGO = 60 -- segundos reais para 1 hora do jogo

task.spawn(function()
	while true do
		local passo = 24 / (MINUTO_DE_JOGO * 60) * 0.5
		Lighting.ClockTime = (Lighting.ClockTime + passo) % 24
		task.wait(0.5)
	end
end)
'''


def _checkpoint() -> str:
    return '''-- ARKHER: checkpoints por spawn
-- Cole em ServerScriptService. Crie Parts no Workspace dentro da pasta
-- "Checkpoints" e nomeie como 1, 2, 3...
local Players = game:GetService("Players")
local pasta = workspace:WaitForChild("Checkpoints")
local progresso = {}

for _, part in ipairs(pasta:GetChildren()) do
	if part:IsA("BasePart") then
		part.Touched:Connect(function(hit)
			local char = hit:FindFirstAncestorOfClass("Model")
			local player = char and Players:GetPlayerFromCharacter(char)
			if not player then return end
			local n = tonumber(part.Name)
			if not n then return end
			if (progresso[player.UserId] or 0) < n then
				progresso[player.UserId] = n
				player.RespawnLocation = part
			end
		end)
	end
end
'''


ROBLOX_TEMPLATES = {
    "leaderstats": _leaderstats,
    "salvamento": _salvamento,
    "teleporte": _teleporte,
    "dia_noite": _dia_noite,
    "checkpoint": _checkpoint,
}


def gerar_roblox(tipo: str) -> dict:
    tipo = (tipo or "").strip().lower()
    if tipo not in ROBLOX_TEMPLATES:
        opcoes = ", ".join(sorted(ROBLOX_TEMPLATES))
        raise ValueError(f"Tipo desconhecido. Opções: {opcoes}")
    codigo = ROBLOX_TEMPLATES[tipo]()
    return {
        "descricao": f"Script Luau gerado pelo gerador determinístico do ARKHER (modelo: {tipo}).",
        "codigo": codigo,
        "como_usar": "Abra o Roblox Studio, cole o script em ServerScriptService e publique. Revise antes de publicar.",
    }


# ------------------------------------------------------------------ OBJ 3D
_ESTILOS_STUDIO = ("lowpoly", "anime", "stylized", "semirealistic", "ultrarealistic", "photorealistic")


def selecionar_estilo(prompt: str) -> dict:
    """Escolhe o StyleProfile do Arkher Studio a partir do pedido (determinístico)."""
    t = _norm(prompt)
    regras = (
        (("low poly", "lowpoly", "minimalista", "performance", "mobile", "a01", "rapido"), "lowpoly",
         "pedido prioriza performance/visual minimalista"),
        (("anime", "cel", "toon", "genshin"), "anime", "pedido cita visual anime/toon"),
        (("fotorreal", "photoreal", "foto real", "realismo maximo", "ultra realista"), "photorealistic",
         "pedido busca fotorrealismo"),
        (("ultra", "aaa", "next gen"), "ultrarealistic", "pedido busca qualidade ultra/AAA"),
        (("semi", "semi-realista", "semirealista"), "semirealistic", "pedido busca semi-realismo"),
        (("estilizado", "stylized", "cartoon", "fofo"), "stylized", "pedido busca visual estilizado"),
    )
    escolha, motivo = "stylized", "padrão equilibrado do ARKHER quando o pedido não especifica estilo"
    for chaves, perfil, razao in regras:
        if any(c in t for c in chaves):
            escolha, motivo = perfil, razao
            break
    return {
        "descricao": f"Estilo '{escolha}' selecionado pelo ARKHER para o pedido.",
        "escolha": escolha,
        "motivo": motivo,
        "opcoes": list(_ESTILOS_STUDIO),
        "como_usar": "Passe 'escolha' para StyleEnhancer:SetStyleProfile() do Studio.",
    }


_TIPOS_FISICA = ("newtonian", "rigidbody", "softbody", "cloth", "fluid", "hair",
                 "muscle", "atomic", "quantum", "relativistic", "thermodynamics",
                 "electromagnetic", "particle", "crowd", "destruction")


def selecionar_fisica(prompt: str) -> dict:
    """Escolhe o PhysicsType do Arkher Studio a partir do pedido (determinístico)."""
    t = _norm(prompt)
    regras = (
        (("roupa", "tecido", "capa", "bandeira", "pano", "cloth"), "cloth", "pedido envolve tecido/roupa"),
        (("agua", "liquido", "fluido", "rio", "oceano"), "fluid", "pedido envolve líquido"),
        (("cabelo", "pelo", "hair"), "hair", "pedido envolve cabelo/pelos"),
        (("gelatina", "macio", "carne", "softbody", "mole"), "softbody", "pedido envolve corpo macio"),
        (("destruicao", "quebrar", "explosao", "destroco", "desmoronar"), "destruction",
         "pedido envolve destruição"),
        (("particula", "fumaca", "fogo", "poeira", "efeito"), "particle", "pedido envolve partículas"),
        (("multidao", "multidões", "npc", "boids", "agentes"), "crowd", "pedido envolve multidão/agentes"),
        (("musculo", "anatomia", "corpo humano"), "muscle", "pedido envolve musculatura"),
        (("gravidade", "basico", "simples", "newton"), "newtonian", "pedido pede física básica"),
        (("veiculo", "caixa", "rigido", "empilhar", "fisica de objetos"), "rigidbody",
         "pedido envolve corpos rígidos"),
    )
    escolha, motivo = "rigidbody", "padrão do ARKHER para física de objetos quando o pedido não especifica"
    for chaves, tipo, razao in regras:
        if any(c in t for c in chaves):
            escolha, motivo = tipo, razao
            break
    return {
        "descricao": f"Física '{escolha}' selecionada pelo ARKHER para o pedido.",
        "escolha": escolha,
        "motivo": motivo,
        "opcoes": list(_TIPOS_FISICA),
        "como_usar": "Passe 'escolha' para PhysicsEngine:SetPhysicsType() do Studio.",
    }


def gerar_terreno_studio(tipo: str, seed: str | None = None) -> dict:
    """Receita de terreno no formato do motor de terreno do Arkher Studio.

    O ARKHER compõe os parâmetros (seed, escala, oitavas, erosão, bioma);
    o motor de terreno do Studio renderiza nativamente com Noise/Erosion dele.
    """
    biomas = ("montanha", "deserto", "planicie", "neve", "vulcao")
    b = (tipo or "").strip().lower()
    if b not in biomas:
        raise ValueError(f"Bioma desconhecido. Opções: {', '.join(biomas)}")
    try:
        semente = int(seed) if seed not in (None, "") else random.randrange(1, 100000)
    except (TypeError, ValueError):
        raise ValueError("seed deve ser um número inteiro")
    rng = random.Random(semente)
    perfis = {
        "montanha": {"heightScale": 48.0, "octaves": 6, "gain": 0.55, "erosao": True,
                     "camadas": [(1, -10, 2), (2, 2, 18), (3, 18, 60)]},
        "deserto": {"heightScale": 10.0, "octaves": 4, "gain": 0.4, "erosao": False,
                    "camadas": [(4, -5, 3), (5, 3, 12)]},
        "planicie": {"heightScale": 6.0, "octaves": 3, "gain": 0.35, "erosao": True,
                     "camadas": [(2, -4, 1), (6, 1, 8)]},
        "neve": {"heightScale": 30.0, "octaves": 5, "gain": 0.5, "erosao": False,
                 "camadas": [(2, -8, 2), (7, 2, 34)]},
        "vulcao": {"heightScale": 40.0, "octaves": 6, "gain": 0.6, "erosao": True,
                   "camadas": [(3, -6, 4), (8, 4, 44)]},
    }
    p = perfis[b]
    settings = {
        "chunkSize": 32,
        "worldSizeChunks": 4,
        "seed": semente,
        "baseHeight": 0.0,
        "heightScale": p["heightScale"] * rng.uniform(0.85, 1.15),
        "noiseType": "perlin",
        "octaves": p["octaves"],
        "lacunarity": round(rng.uniform(1.9, 2.2), 3),
        "gain": p["gain"],
        "enableErosion": p["erosao"],
        "enableBiomes": True,
        "enableCaves": b in ("montanha", "vulcao"),
        "materialLayers": [
            {"materialId": mid, "minHeight": mn, "maxHeight": mx}
            for mid, mn, mx in p["camadas"]
        ],
    }
    # amostra central do heightfield (16x16) p/ preview rápido sem o motor
    amostras = []
    fases = [(rng.uniform(0, math.tau), rng.uniform(0.3, 1.2)) for _ in range(3)]
    for iz in range(16):
        linha = []
        for ix in range(16):
            h = 0.0
            for fase, freq in fases:
                h += math.sin(ix * freq + fase) * math.cos(iz * freq + fase)
            linha.append(round(h / 3 * settings["heightScale"] / 10, 3))
        amostras.append(linha)
    return {
        "descricao": f"Receita de terreno '{b}' (seed {semente}) para o motor de terreno do Arkher Studio.",
        "bioma": b,
        "settings": settings,
        "amostras_16x16": amostras,
        "como_usar": "Passe 'settings' para TerrainData.new() do Studio; o Noise/Erosion nativos renderizam.",
    }


def gerar_animacao(tipo: str, seed: str | None = None, duracao: float = 2.0) -> dict:
    """Keyframes procedurais prontos para animadores (UniversalAnimator etc.).

    Saída em trilhas {propriedade, keyframes:[{t, valor}]} onde valor é lista
    [x,y,z] (vira Vector3 no consumidor) ou número. Determinístico pela seed.
    """
    tipos = ("girar", "flutuar", "pulsar", "vaivem", "tremer")
    t = (tipo or "").strip().lower()
    if t not in tipos:
        raise ValueError(f"Tipo desconhecido. Opções: {', '.join(tipos)}")
    try:
        semente = int(seed) if seed not in (None, "") else random.randrange(1, 100000)
    except (TypeError, ValueError):
        raise ValueError("seed deve ser um número inteiro")
    duracao = max(0.5, min(10.0, float(duracao)))
    rng = random.Random(semente)
    n = 12
    tempos = [round(duracao * i / (n - 1), 4) for i in range(n)]
    trilhas: list[dict] = []
    if t == "girar":
        angulo = 360.0 if rng.random() > 0.25 else -360.0
        trilhas.append({
            "propriedade": "Rotation",
            "keyframes": [{"t": k, "valor": [0, angulo * k / duracao, 0]} for k in tempos],
        })
    elif t == "flutuar":
        amp = rng.uniform(1.0, 2.5)
        fase = rng.uniform(0, math.tau)
        trilhas.append({
            "propriedade": "PositionOffsetY",
            "keyframes": [{"t": k, "valor": round(math.sin(k / duracao * math.tau + fase) * amp, 4)} for k in tempos],
        })
    elif t == "pulsar":
        base, amp = 1.0, rng.uniform(0.15, 0.45)
        trilhas.append({
            "propriedade": "SizeScale",
            "keyframes": [{"t": k, "valor": round(base + math.sin(k / duracao * math.tau) * amp, 4)} for k in tempos],
        })
    elif t == "vaivem":
        amp = rng.uniform(2.0, 6.0)
        trilhas.append({
            "propriedade": "PositionOffsetX",
            "keyframes": [{"t": k, "valor": round(math.sin(k / duracao * math.tau) * amp, 4)} for k in tempos],
        })
    else:  # tremer
        trilhas.append({
            "propriedade": "PositionOffset",
            "keyframes": [{"t": k, "valor": [round(rng.uniform(-0.4, 0.4), 3), 0, round(rng.uniform(-0.4, 0.4), 3)]} for k in tempos],
        })
    return {
        "descricao": f"Animação '{t}' ({duracao}s, {n} keyframes, seed {semente}) gerada pelo ARKHER.",
        "tipo": t,
        "duracao": duracao,
        "fps": 30,
        "trilhas": trilhas,
        "como_usar": "Registre o objeto no animador e aplique cada keyframe (valor em lista vira Vector3).",
    }


def gerar_terreno(seed: str | None = None, tamanho: int = 16, amplitude: float = 2.5) -> dict:
    """Gera um terreno heightmap em OBJ (texto), determinístico pela seed."""
    try:
        semente = int(seed) if seed not in (None, "") else random.randrange(1, 100000)
    except (TypeError, ValueError):
        raise ValueError("seed deve ser um número inteiro")
    tamanho = max(8, min(32, int(tamanho)))
    rng = random.Random(semente)
    fases = [(rng.uniform(0, math.tau), rng.uniform(0.4, 1.6), rng.uniform(0.5, 1.5)) for _ in range(4)]

    def altura(x: float, z: float) -> float:
        h = 0.0
        for fase, freq, peso in fases:
            h += math.sin(x * freq + fase) * math.cos(z * freq * 0.9 + fase * 0.7) * peso
        return h * amplitude / 2

    linhas = [
        f"# Terreno ARKHER — seed {semente}, grade {tamanho}x{tamanho}",
        "# Importe no Blender ou em qualquer engine que leia OBJ.",
    ]
    grade: list[list[int]] = []
    idx = 1
    for iz in range(tamanho):
        linha = []
        for ix in range(tamanho):
            h = altura(ix, iz)
            linhas.append(f"v {ix:.2f} {h:.3f} {iz:.2f}")
            linha.append(idx)
            idx += 1
        grade.append(linha)
    for iz in range(tamanho - 1):
        for ix in range(tamanho - 1):
            a, b = grade[iz][ix], grade[iz][ix + 1]
            c, d = grade[iz + 1][ix], grade[iz + 1][ix + 1]
            linhas.append(f"f {a} {b} {d} {c}")
    conteudo = "\n".join(linhas) + "\n"
    return {
        "descricao": f"Terreno heightmap {tamanho}x{tamanho} (seed {semente}) gerado pelo ARKHER.",
        "arquivo": {"nome": f"terreno_arkher_{semente}.obj", "conteudo": conteudo},
        "como_usar": "Baixe o arquivo .obj e importe no Blender ou na sua engine.",
    }
