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

return Connector
