-- ARKHER Ponte v1 — construção ao vivo no Roblox Studio
--
-- Instalação: salve este arquivo na pasta de plugins do Roblox Studio
--   Windows: %LOCALAPPDATA%\Roblox\Plugins\ArkherPonte.lua
--   (ou arraste o arquivo para a janela do Studio uma vez)
--
-- Uso: peça uma construção no chat da ARKHER (ex.: "crie uma base do
-- exército brasileiro no roblox studio"), depois clique em
-- "Construir agora" aqui no plugin. Ela busca o stream de construção e
-- monta peça por peça, em tempo real, dentro da place aberta.
--
-- Você controla o Studio. A ARKHER só constrói. Nada aqui toca sua
-- máquina além de falar com o servidor ARKHER que VOCÊ configurar.

local HttpService = game:GetService("HttpService")

local URL_PADRAO = "http://127.0.0.1:8710"

local toolbar = plugin:CreateToolbar("ARKHER")

local widgetInfo = DockWidgetPluginGuiInfo.new(
	Enum.InitialDockState.Right, false, false, 280, 240, 240, 220
)
local widget = plugin:CreateDockWidgetPluginGui("ArkherPonte", widgetInfo)
widget.Title = "ARKHER Ponte"
widget.Name = "ArkherPonteWidget"

local raiz = Instance.new("Frame")
raiz.Size = UDim2.fromScale(1, 1)
raiz.BackgroundTransparency = 1
raiz.Parent = widget

local function rotulo(texto, topo)
	local l = Instance.new("TextLabel")
	l.Size = UDim2.new(1, -8, 0, 16)
	l.Position = UDim2.new(0, 4, 0, topo)
	l.BackgroundTransparency = 1
	l.TextXAlignment = Enum.TextXAlignment.Left
	l.TextSize = 12
	l.Text = texto
	l.Parent = raiz
	return l
end

local function caixa(topo, dica)
	local c = Instance.new("TextBox")
	c.Size = UDim2.new(1, -8, 0, 22)
	c.Position = UDim2.new(0, 4, 0, topo)
	c.PlaceholderText = dica
	c.Text = ""
	c.TextSize = 12
	c.ClearTextOnFocus = false
	c.Parent = raiz
	return c
end

rotulo("Servidor ARKHER:", 4)
local caixaUrl = caixa(20, URL_PADRAO)
rotulo("Token (aba Configurações → Dispositivos):", 48)
local caixaToken = caixa(64, "cole seu token aqui")

local botao = Instance.new("TextButton")
botao.Size = UDim2.new(1, -8, 0, 28)
botao.Position = UDim2.new(0, 4, 0, 92)
botao.Text = "Construir agora"
botao.TextSize = 14
botao.BackgroundColor3 = Color3.fromRGB(46, 160, 67)
botao.TextColor3 = Color3.fromRGB(255, 255, 255)
botao.Parent = raiz

local statusLbl = rotulo("Pronto.", 128)
statusLbl.TextWrapped = true
statusLbl.Size = UDim2.new(1, -8, 0, 60)

caixaUrl.Text = plugin:GetSetting("ARKHER_URL") or ""
caixaToken.Text = plugin:GetSetting("ARKHER_TOKEN") or ""

local function montar(pasta, ops)
	for _, op in ipairs(ops) do
		if op.op == "part" then
			local p = Instance.new("Part")
			p.Name = op.nome or "Part"
			p.Anchored = true
			p.Size = Vector3.new(op.size[1], op.size[2], op.size[3])
			p.CFrame = CFrame.new(op.pos[1], op.pos[2], op.pos[3])
			p.Color = Color3.fromRGB(op.cor[1], op.cor[2], op.cor[3])
			p.Parent = pasta
		end
		task.wait(0.02) -- construção visível, peça por peça
	end
end

local function buscar()
	local url = caixaUrl.Text ~= "" and caixaUrl.Text or URL_PADRAO
	local token = caixaToken.Text
	if token == "" then
		statusLbl.Text = "Cole seu token ARKHER primeiro."
		return
	end
	plugin:SetSetting("ARKHER_URL", caixaUrl.Text)
	plugin:SetSetting("ARKHER_TOKEN", token)
	statusLbl.Text = "Buscando construção…"
	task.spawn(function()
		local ok, resp = pcall(function()
			return HttpService:RequestAsync({
				Url = url .. "/api/build/proximo",
				Method = "GET",
				Headers = { ["X-Arkher-Token"] = token },
			})
		end)
		if not ok or not resp.Success then
			statusLbl.Text = "Falha ao falar com o servidor ARKHER."
			return
		end
		local ok2, dados = pcall(HttpService.JSONDecode, HttpService, resp.Body)
		if not ok2 or not dados or not dados.build_id then
			statusLbl.Text = "Nenhuma construção pendente. Peça uma no chat primeiro."
			return
		end
		local antiga = workspace:FindFirstChild("ARKHER_Build")
		if antiga then antiga:Destroy() end
		local pasta = Instance.new("Folder")
		pasta.Name = "ARKHER_Build"
		pasta.Parent = workspace
		statusLbl.Text = "Construindo '" .. tostring(dados.tema) .. "'…"
		montar(pasta, dados.ops)
		statusLbl.Text = "Concluído: " .. tostring(#dados.ops) .. " peças na pasta ARKHER_Build."
	end)
end

botao.MouseButton1Click:Connect(buscar)

local abrir = toolbar:CreateButton("Ponte ARKHER", "Abrir painel de construção ao vivo", "")
abrir.Click:Connect(function()
	widget.Enabled = not widget.Enabled
end)
