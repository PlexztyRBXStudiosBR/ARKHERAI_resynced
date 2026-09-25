-- ARKHER AI | instalador do Studio Lite via Command Bar
-- Cole tudo no Command Bar e execute uma vez no modo de edicao.
-- O script cria a ponte local; nao executa codigo remoto nem usa executor.
local RS = game:GetService("ReplicatedStorage")
local SSS = game:GetService("ServerScriptService")
local SPS = game:GetService("StarterPlayer"):WaitForChild("StarterPlayerScripts")
local SG = game:GetService("StarterGui")

local function folder(parent, name)
    local x = parent:FindFirstChild(name)
    if not x then x = Instance.new("Folder"); x.Name = name; x.Parent = parent end
    return x
end
local function module(parent, name, source)
    local x = parent:FindFirstChild(name)
    if not x then x = Instance.new("ModuleScript"); x.Name = name; x.Parent = parent end
    x.Source = source
    return x
end
local function localScript(parent, name, source)
    local x = parent:FindFirstChild(name)
    if not x then x = Instance.new("LocalScript"); x.Name = name; x.Parent = parent end
    x.Source = source
    return x
end

local root = folder(RS, "ArkherAI")
local events = folder(root, "Events")
local assets = folder(root, "Assets")
folder(root, "Cache")
folder(root, "Generated")
folder(root, "Knowledge")

local config = module(root, "Config", [[
return {
    Backend = "http://127.0.0.1:8710",
    StudioProxy = "http://127.0.0.1:3000/api/arkherai",
    Enabled = true,
    -- Cole aqui o token de dispositivo apenas se o seu proxy exigir.
    Token = "",
}
]])

module(root, "ClientBridge", [[
local HttpService = game:GetService("HttpService")
local Config = require(script.Parent.Config)
local Bridge = {}
function Bridge.Request(path, body)
    if not Config.Enabled then return false, "ARKHER_AI_DESATIVADA" end
    local ok, result = pcall(function()
        return HttpService:RequestAsync({
            Url = Config.StudioProxy .. path,
            Method = "POST", Headers = { ["Content-Type"] = "application/json" },
            Body = HttpService:JSONEncode(body or {}),
        })
    end)
    if not ok or not result.Success then return false, (result and result.StatusMessage) or "BACKEND_OFFLINE" end
    local decoded = pcall(HttpService.JSONDecode, HttpService, result.Body)
    if not decoded then return false, "RESPOSTA_INVALIDA" end
    return true, HttpService:JSONDecode(result.Body)
end
return Bridge
]])

module(SSS, "ArkherAI_Server", [[
-- Ponto seguro para materializadores aprovados. A IA nao ganha permissao de
-- publicar, apagar ou executar codigo arbitrario; o jogo decide o que aceita.
local M = {}
M.Root = game:GetService("ReplicatedStorage"):WaitForChild("ArkherAI")
return M
]])

local gui = Instance.new("ScreenGui")
gui.Name = "ArkherAI_Toolbar"
gui.ResetOnSpawn = false
gui.DisplayOrder = 1000
gui.Parent = SG
local button = Instance.new("TextButton")
button.Name = "ArkherAI"
button.Size = UDim2.fromOffset(118, 30)
button.Position = UDim2.new(0, 180, 0, 8)
button.BackgroundColor3 = Color3.fromRGB(10, 10, 10)
button.TextColor3 = Color3.fromRGB(225, 180, 55)
button.Text = "ArkherAI"
button.Font = Enum.Font.GothamBold
button.TextSize = 14
button.Visible = false
button.Parent = gui
local corner = Instance.new("UICorner"); corner.CornerRadius = UDim.new(0, 5); corner.Parent = button
local stroke = Instance.new("UIStroke"); stroke.Color = Color3.fromRGB(225, 180, 55); stroke.Thickness = 2; stroke.Parent = button
local panel = Instance.new("Frame")
panel.Name = "Panel"
panel.Size = UDim2.fromOffset(390, 430)
panel.Position = UDim2.new(1, -405, 0, 48)
panel.BackgroundColor3 = Color3.fromRGB(15, 17, 16)
panel.Visible = false
panel.Parent = gui
local title = Instance.new("TextLabel"); title.Size = UDim2.new(1, -20, 0, 34); title.Position = UDim2.fromOffset(10, 8); title.BackgroundTransparency = 1; title.Text = "ARKHER AI • Studio Lite"; title.TextColor3 = Color3.fromRGB(225,180,55); title.Font = Enum.Font.GothamBold; title.TextSize = 16; title.TextXAlignment = Enum.TextXAlignment.Left; title.Parent = panel
local info = Instance.new("TextLabel"); info.Size = UDim2.new(1,-20,1,-55); info.Position = UDim2.fromOffset(10,48); info.BackgroundTransparency=1; info.TextWrapped=true; info.TextYAlignment=Enum.TextYAlignment.Top; info.TextXAlignment=Enum.TextXAlignment.Left; info.TextColor3=Color3.fromRGB(220,220,220); info.Font=Enum.Font.Gotham; info.TextSize=13; info.Text="Painel instalado. Configure o proxy e conecte o AgentPanel do Studio.\n\nAbas previstas: Chat • 3D • Anim • Jogo • Web.\n\nO renderizador/importador deve rodar no backend autorizado; este painel nao executa scripts recebidos."; info.Parent=panel
localScript(SPS, "ArkherAI_ToolbarClient", [[
local RunService = game:GetService("RunService")
local gui = game:GetService("Players").LocalPlayer:WaitForChild("PlayerGui"):WaitForChild("ArkherAI_Toolbar", 5)
if not gui then return end
local b = gui:FindFirstChild("ArkherAI"); local p = gui:FindFirstChild("Panel")
if not b or not p then return end
-- O Studio Lite pode nao expor um evento de retorno ao modo edit. O botao
-- fica oculto durante Play e aparece novamente ao retornar ao editor quando
-- o ambiente fornecer essa transicao.
b.Visible = not RunService:IsRunning()
b.MouseButton1Click:Connect(function() p.Visible = not p.Visible end)
RunService.Heartbeat:Connect(function()
    local edit = not RunService:IsRunning()
    if b.Visible ~= edit and not p.Visible then b.Visible = edit end
end)
]])
print("ARKHER AI instalado: ReplicatedStorage.ArkherAI + ServerScriptService.ArkherAI_Server + StarterPlayerScripts.ArkherAI_ToolbarClient + StarterGui.ArkherAI_Toolbar")
