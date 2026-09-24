--!strict
-- ArkherAIConnector — integração REAL do ARKHER AI com o Arkher Studio.
--
-- O ARKHER AI (backend próprio + modelo próprio) expõe API HTTP:
--   POST /api/auth/device      → registra o dispositivo e devolve token
--   GET  /api/health           → estado do backend/modelo
--   POST /api/chat             → conversa (resposta em SSE; o corpo completo
--                                 chega ao fim da geração — parse abaixo)
--   POST /api/tools/{id}/authorize → autoriza uma ferramenta
--   POST /api/build/start      → pede uma construção (tema livre + seed)
--   GET  /api/build/proximo    → busca as operações (peça por peça)
--
-- Este módulo conversa DIRETO com o backend do ARKHER (configure a URL).
-- Nada de mock: se o backend estiver fora, devolve erro honesto.
--
-- Uso:
--   local ArkherAI = require(script.Parent.ArkherAIConnector)
--   ArkherAI.Configurar("http://SEU_SERVIDOR:8710")
--   local ok, resposta = ArkherAI.Chat("crie um castelo medieval com torres")
--   local build = ArkherAI.Construir("castelo medieval", 11)
--   ArkherAI.Materializar(build.ops)  -- cria as peças no Workspace

local HttpService = game:GetService("HttpService")

local Connector = {}

local _baseUrl: string = ""
local _token: string = ""

-- ------------------------------------------------------------------ config
function Connector.Configurar(url: string): ()
	_baseUrl = url:gsub("/$", "") -- sem barra final
	_token = ""
end

function Connector.UrlAtual(): string
	return _baseUrl
end

-- ------------------------------------------------------------------ http
local function request(method: string, path: string, body: any?): (boolean, any)
	if _baseUrl == "" then
		return false, { error = "Configure a URL do backend ARKHER com Configurar()." }
	end
	local headers = { ["Content-Type"] = "application/json" }
	if _token ~= "" then
		headers["Authorization"] = "Bearer " .. _token
		headers["X-Arkher-Token"] = _token -- fallback para proxies
	end
	local ok, res = pcall(function()
		return HttpService:RequestAsync({
			Url = _baseUrl .. path,
			Method = method,
			Headers = headers,
			Body = body ~= nil and HttpService:JSONEncode(body) or nil,
		})
	end)
	if not ok then
		return false, { error = tostring(res) }
	end
	local r = res :: any
	if not r.Success then
		return false, { error = ("HTTP %d"):format(r.StatusCode), body = r.Body }
	end
	local decoded = nil
	if r.Body and r.Body ~= "" then
		local jok, jres = pcall(HttpService.JSONDecode, HttpService, r.Body)
		decoded = jok and jres or r.Body
	end
	return true, decoded
end

-- SSE do /api/chat: eventos "event: X" + "data: {json}", um por linha
local function parseSSE(corpo: string): { done: any?, tokens: number, erro: any? }
	local donePayload = nil
	local tokenCount = 0
	local erroPayload = nil
	local eventoAtual = nil
	for linha in (corpo .. "\n"):gmatch("(.-)\n") do
		if linha:sub(1, 7) == "event: " then
			eventoAtual = linha:sub(8)
		elseif linha:sub(1, 6) == "data: " then
			local jok, dados = pcall(HttpService.JSONDecode, HttpService, linha:sub(7))
			if jok and eventoAtual then
				if eventoAtual == "done" then
					donePayload = dados
				elseif eventoAtual == "token" then
					tokenCount += 1
				elseif eventoAtual == "error" then
					erroPayload = dados
				end
			end
		end
	end
	return { done = donePayload, tokens = tokenCount, erro = erroPayload }
end

-- ------------------------------------------------------------------ auth/status
function Connector.Registrar(nomeDoDispositivo: string?): (boolean, any)
	local ok, res = request("POST", "/api/auth/device", { name = nomeDoDispositivo or "Arkher Studio" })
	if ok and res and res.token then
		_token = res.token
		return true, res
	end
	return false, res
end

function Connector.Saude(): (boolean, any)
	local ok, res = request("GET", "/api/health")
	return ok, res
end

function Connector.StatusModelo(): (boolean, any)
	local ok, res = request("GET", "/api/model/status")
	return ok, res
end

-- ------------------------------------------------------------------ chat
function Connector.Chat(mensagem: string, sessionId: string?, memoria: boolean?): (boolean, any)
	if _token == "" then
		local regOk = Connector.Registrar()
		if not regOk then
			return false, { error = "Sem token: backend ARKHER inacessível." }
		end
	end
	local ok, res = request("POST", "/api/chat", {
		message = mensagem,
		session_id = sessionId,
		memory_enabled = memoria ~= false,
	})
	if not ok then
		return false, res
	end
	if typeof(res) == "table" and res.content then
		-- resposta já veio como JSON simples
		return true, res
	end
	if typeof(res) == "string" then
		local sse = parseSSE(res)
		if sse.erro then
			return false, sse.erro
		end
		if sse.done then
			return true, sse.done
		end
	end
	return false, { error = "Resposta inesperada do backend." }
end

-- ------------------------------------------------------------------ construção
function Connector.Construir(tema: string, seed: number?): (boolean, any)
	if _token == "" then
		Connector.Registrar()
	end
	request("POST", "/api/tools/build_gen/authorize")
	local ok, res = request("POST", "/api/build/start", {
		tema = tema,
		seed = seed or 42,
	})
	if not ok then
		return false, res
	end
	local okOps, ops = request("GET", "/api/build/proximo")
	if not okOps then
		return false, ops
	end
	return true, ops
end

-- Materializa as operações como peças reais (cliente/Studio).
-- Devolve o Folder criado para você anexar onde quiser (ECS, Projeto, Workspace).
function Connector.Materializar(ops: { any }, pastaPai: Instance?): Instance?
	if typeof(ops) ~= "table" then
		return nil
	end
	local pasta = Instance.new("Folder")
	pasta.Name = "ArkherBuild_" .. os.time()
	pasta.Parent = pastaPai or workspace
	for _, op in ops do
		if typeof(op) == "table" and op.op == "part" then
			local p = Instance.new("Part")
			p.Name = tostring(op.nome or "Peca")
			local pos = op.pos or { 0, 0, 0 }
			local size = op.size or { 4, 4, 4 }
			local cor = op.cor or { 160, 160, 160 }
			p.Position = Vector3.new(pos[1], pos[2], pos[3])
			p.Size = Vector3.new(size[1], size[2], size[3])
			p.Color = Color3.fromRGB(cor[1], cor[2], cor[3])
			p.Anchored = op.ancorado ~= false
			p.TopSurface = Enum.SurfaceType.Smooth
			p.BottomSurface = Enum.SurfaceType.Smooth
			p.Parent = pasta
		end
	end
	return pasta
end

-- ------------------------------------------------------------------ modeler
-- Parseia o OBJ que o ARKHER gera (obj_gen) em geometria pura.
function Connector.ParseOBJ(texto: string): { vertices: { { number } }, faces: { { number } } }
	local vertices: { { number } } = {}
	local faces: { { number } } = {}
	for linha in (texto .. "\n"):gmatch("(.-)\n") do
		local vx, vy, vz = linha:match("^v%s+([%-%d%.]+)%s+([%-%d%.]+)%s+([%-%d%.]+)")
		if vx then
			table.insert(vertices, { tonumber(vx) or 0, tonumber(vy) or 0, tonumber(vz) or 0 })
		else
			local f = linha:match("^f%s+(.+)$")
			if f then
				local ids: { number } = {}
				for tok in f:gmatch("%S+") do
					local id = tonumber(tok:match("^(%d+)"))
					if id then
						table.insert(ids, id)
					end
				end
				if #ids >= 3 then
					table.insert(faces, ids)
				end
			end
		end
	end
	return { vertices = vertices, faces = faces }
end

-- Gera mesh real no ARKHER (terreno heightmap OBJ) e devolve geometria.
function Connector.GerarMesh(seed: number?): (boolean, any)
	if _token == "" then
		Connector.Registrar()
	end
	request("POST", "/api/tools/obj_gen/authorize")
	local ok, res = request("POST", "/api/tools/obj_gen/run", { seed = tostring(seed or 42) })
	if not ok or typeof(res) ~= "table" then
		return false, res
	end
	local resultado = (res :: any).result
	if not resultado or not resultado.arquivo or not resultado.arquivo.conteudo then
		return false, { error = "Resposta sem geometria." }
	end
	local geo = Connector.ParseOBJ(resultado.arquivo.conteudo)
	return true, {
		geometria = geo,
		descricao = resultado.descricao,
		nome = resultado.arquivo.nome,
		vertices = #geo.vertices,
		faces = #geo.faces,
	}
end

-- Converte a geometria do ARKHER no MeshData do Arkher Studio
-- (passe o módulo MeshData: require(script.Parent.Parent.Modeling.MeshData)).
function Connector.ParaMeshData(geometria: any, MeshData: any): any
	local mesh = MeshData.new()
	for _, v in geometria.vertices do
		MeshData.AddVertex(mesh, Vector3.new(v[1], v[2], v[3]))
	end
	for _, face in geometria.faces do
		MeshData.AddFace(mesh, face)
	end
	return mesh
end

-- Interface no formato que o ArkherEngineerResource espera
-- (engineer.arkherAI = Connector.InterfaceIA()).
-- GenerateModel devolve contagens REAIS + a geometria em .dados — quem quiser
-- montar o mesh de verdade usa Connector.ParaMeshData(resultado.dados, MeshData).
function Connector.InterfaceIA(): any
	return {
		GenerateModel = function(_self, prompt: string, styleProfile: string?)
			local ok, res = Connector.GerarMesh()
			if not ok then
				return { mesh = { vertices = 0, triangles = 0 }, styleProfile = styleProfile or "realistic", message = tostring((res or {}).error or "backend fora") }
			end
			return {
				mesh = {
					vertices = res.vertices,
					triangles = res.faces * 2,
					format = "EditableMesh",
					dados = res.geometria,
					generatedBy = "ARKHER AI - backend proprio",
				},
				styleProfile = styleProfile or "realistic",
				message = res.descricao,
			}
		end,
		GenerateTexture = function(_self, prompt: string, styleProfile: string?, resolucao: string?)
			return {
				resolution = resolucao or "4K",
				generatedBy = "ARKHER AI - textura tileable via Blender (cenas textura_* no backend)",
				message = "Peça a textura na aba 3D do ARKHER (textura_pedra/tijolo/metal/madeira) e aplique como tile.",
			}
		end,
	}
end

-- ------------------------------------------------------------------ animator
-- Gera keyframes procedurais no ARKHER (girar/flutuar/pulsar/vaivem/tremer).
function Connector.GerarAnimacao(tipo: string, seed: number?, duracao: number?): (boolean, any)
	if _token == "" then
		Connector.Registrar()
	end
	request("POST", "/api/tools/anim_gen/authorize")
	return request("POST", "/api/tools/anim_gen/run", {
		tipo = tipo,
		seed = tostring(seed or 42),
		duracao = duracao or 2.0,
	})
end

-- Aplica as trilhas do ARKHER num UniversalAnimator do Arkher Studio:
--   local ok, anim = ArkherAI.GerarAnimacao("flutuar", 7)
--   ArkherAI.AplicarAnimacao(animator, minhaPart, anim.result)
function Connector.AplicarAnimacao(animator: any, objeto: Instance, anim: any): number?
	if typeof(anim) ~= "table" or not anim.trilhas then
		return nil
	end
	local track = animator:RegisterObject(objeto, "Part")
	local basePos = objeto:IsA("BasePart") and objeto.Position or Vector3.new()
	local baseSize = objeto:IsA("BasePart") and objeto.Size or Vector3.new(1, 1, 1)
	local aplicados = 0
	for _, trilha in anim.trilhas do
		local prop = trilha.propriedade
		for _, kf in trilha.keyframes do
			local valor = kf.valor
			local propriedade, v = prop, valor
			if prop == "Rotation" and typeof(valor) == "table" then
				v = Vector3.new(valor[1], valor[2], valor[3])
			elseif prop == "PositionOffsetY" and typeof(valor) == "number" then
				propriedade, v = "Position", basePos + Vector3.new(0, valor, 0)
			elseif prop == "PositionOffsetX" and typeof(valor) == "number" then
				propriedade, v = "Position", basePos + Vector3.new(valor, 0, 0)
			elseif prop == "PositionOffset" and typeof(valor) == "table" then
				propriedade, v = "Position", basePos + Vector3.new(valor[1], valor[2], valor[3])
			elseif prop == "SizeScale" and typeof(valor) == "number" then
				propriedade, v = "Size", baseSize * valor
			end
			animator:AddKeyframe(track.id, propriedade, kf.t, v, "humanized")
			aplicados += 1
		end
	end
	return aplicados
end

-- ------------------------------------------------------------------ terreno
-- Receita de terreno do ARKHER no formato do motor TerrainData do Studio.
function Connector.Terreno(bioma: string, seed: number?): (boolean, any)
	if _token == "" then
		Connector.Registrar()
	end
	request("POST", "/api/tools/terrain_gen/authorize")
	local ok, res = request("POST", "/api/tools/terrain_gen/run", {
		bioma = bioma,
		seed = tostring(seed or 42),
	})
	if not ok or typeof(res) ~= "table" then
		return false, res
	end
	return true, (res :: any).result
end

-- O 'settings' da receita já é aceito por TerrainData.new() do Studio.
function Connector.ParaTerrenoDoStudio(receita: any): any?
	if typeof(receita) ~= "table" or receita.settings == nil then
		return nil
	end
	return receita.settings
end

-- ------------------------------------------------------------------ ECS
-- Converte as operações de build em entidades ECS (World do Arkher Studio).
function Connector.ParaEntidades(ops: { any }, Entity: any, World: any, world: any): number
	if typeof(ops) ~= "table" then
		return 0
	end
	local n = 0
	for _, op in ops do
		if typeof(op) == "table" and op.op == "part" then
			local e = Entity.new(tostring(op.nome or "Peca"))
			local pos = op.pos or { 0, 0, 0 }
			local size = op.size or { 4, 4, 4 }
			local cor = op.cor or { 160, 160, 160 }
			Entity.AddComponent(e, "Transform", {
				position = Vector3.new(pos[1], pos[2], pos[3]),
				size = Vector3.new(size[1], size[2], size[3]),
			})
			Entity.AddComponent(e, "Render", {
				color = Color3.fromRGB(cor[1], cor[2], cor[3]),
				visible = true,
			})
			Entity.AddTag(e, "arkher")
			world:AddEntity(e)
			n += 1
		end
	end
	return n
end

-- Serializa o mundo (com as entidades ARKHER) no formato .arkher do Studio.
function Connector.SerializarProjeto(world: any, ProjectFormat: any, meta: any?): string?
	local ok, json = pcall(ProjectFormat.Serialize, world, meta or { geradoPor = "ARKHER AI" })
	return ok and json or nil
end

-- ------------------------------------------------------------------ estilo (ANG)
-- O ARKHER escolhe o StyleProfile a partir do pedido.
function Connector.Estilo(prompt: string): (boolean, any)
	if _token == "" then
		Connector.Registrar()
	end
	request("POST", "/api/tools/style_gen/authorize")
	local ok, res = request("POST", "/api/tools/style_gen/run", { prompt = prompt })
	if not ok or typeof(res) ~= "table" then
		return false, res
	end
	return true, (res :: any).result
end

-- Aplica o perfil escolhido no StyleEnhancer (ANG) do Studio.
function Connector.AplicarEstilo(enhancer: any, perfil: string?): boolean
	if enhancer == nil or typeof(perfil) ~= "string" then
		return false
	end
	local ok = pcall(function()
		enhancer:SetStyleProfile(perfil)
	end)
	return ok
end

-- ------------------------------------------------------------------ física
-- O ARKHER escolhe o PhysicsType a partir do pedido.
function Connector.Fisica(prompt: string): (boolean, any)
	if _token == "" then
		Connector.Registrar()
	end
	request("POST", "/api/tools/fisica_gen/authorize")
	local ok, res = request("POST", "/api/tools/fisica_gen/run", { prompt = prompt })
	if not ok or typeof(res) ~= "table" then
		return false, res
	end
	return true, (res :: any).result
end

-- Aplica o tipo escolhido no PhysicsEngine do Studio.
function Connector.AplicarFisica(engine: any, tipo: string?): boolean
	if engine == nil or typeof(tipo) ~= "string" then
		return false
	end
	local ok = pcall(function()
		engine:SetPhysicsType(tipo)
	end)
	return ok
end

-- ------------------------------------------------------------------ código
-- O modelo do ARKHER como gerador de código (Luau/Python) para o Scripting.
function Connector.Codigo(prompt: string): (boolean, any)
	return Connector.Chat("Gere apenas o código pedido, sem explicações: " .. prompt)
end

-- ------------------------------------------------------------------ vault
-- Registra um asset gerado pelo ARKHER no formato esperado pelo Arkher Vault.
function Connector.ParaVault(mesh: any, nome: string?): any
	return {
		name = nome or ("arkher_asset_" .. os.time()),
		type = "model",
		source = "arkher_ai",
		mesh = mesh,
		tags = { "arkher", "generated" },
	}
end

-- ------------------------------------------------------------------ cobertura
-- Mapa honesto do que está ligado e do que não tem correspondência no ARKHER.
function Connector.Cobertura(): { [string]: string }
	return {
		Building = "ligado — Construir/Materializar (Parts) e ParaEntidades (ECS)",
		Modeling = "ligado — GerarMesh/ParaMeshData (EditableMesh) e InterfaceIA",
		Animation = "ligado — GerarAnimacao/AplicarAnimacao (UniversalAnimator)",
		Terrain = "ligado — Terreno/ParaTerrenoDoStudio (TerrainData nativo)",
		Serialization = "ligado — SerializarProjeto (ProjectFormat .arkher)",
		Scripting = "ligado — Codigo (modelo proprio gera Luau/Python)",
		Vault = "ligado — ParaVault (registro de assets gerados)",
		Chat = "ligado — Chat (SSE consumido)",
		ANG = "ligado (estilo) — Estilo/AplicarEstilo escolhe e aplica o StyleProfile no StyleEnhancer; frame-gen/super-res continuam sendo do proprio ANG",
		Physics = "ligado (selecao) — Fisica/AplicarFisica escolhe e aplica o PhysicsType; a simulacao e do PhysicsEngine do Studio",
		Input = "lado do Studio — nao se aplica",
		Publish = "lado do Studio (Open Cloud) - nao se aplica",
	}
end

return Connector
