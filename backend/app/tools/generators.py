"""Geradores game dev do ARKHER — ferramentas determinísticas do próprio projeto.

Produzem código e assets reais para o usuário usar nas ferramentas DELE
(Roblox Studio, Blender/engines que importam OBJ), com revisão humana.
Nenhuma máquina é controlada remotamente.
"""
from __future__ import annotations

import math
import random


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
