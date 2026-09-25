-- ARKHER AI Training Plugin
-- Instale em Roblox Studio: Plugins > Plugin Folder.
-- Processa o DataModel que estiver aberto; o treino de 6h é iniciado pelo .cmd.
local HttpService = game:GetService("HttpService")
local toolbar = plugin:CreateToolbar("ARKHER AI")
local open = toolbar:CreateButton("ArkherAI", "Analisar projeto e enviar manifest", "")
local info = DockWidgetPluginGuiInfo.new(Enum.InitialDockState.Right, true, false, 360, 280, 280, 200)
local widget = plugin:CreateDockWidgetPluginGui("ArkherAITraining", info)
widget.Title = "ArkherAI Training"
local label = Instance.new("TextLabel")
label.Size = UDim2.fromScale(1,1); label.BackgroundColor3=Color3.fromRGB(12,14,14); label.TextColor3=Color3.fromRGB(225,180,55); label.TextWrapped=true; label.TextYAlignment=Enum.TextYAlignment.Top; label.TextXAlignment=Enum.TextXAlignment.Left; label.Font=Enum.Font.Code; label.TextSize=13; label.Text="Clique em ArkherAI para analisar o projeto aberto."; label.Parent=widget
local function scan()
 local counts={}; local scripts={}; local remotes={}; local nodes=0
 for _,x in ipairs(game:GetDescendants()) do
  nodes+=1; counts[x.ClassName]=(counts[x.ClassName] or 0)+1
  if x:IsA("LuaSourceContainer") then table.insert(scripts,{name=x:GetFullName(),class=x.ClassName}) end
  if x:IsA("RemoteEvent") or x:IsA("RemoteFunction") then table.insert(remotes,{name=x:GetFullName(),class=x.ClassName}) end
 end
 local data={schema="arkher-studio-manifest-v1",placeId=game.PlaceId,nodes=nodes,classes=counts,scripts=scripts,remotes=remotes,created=os.date("!*t")}
 return data
end
local function run()
 widget.Enabled=true; label.Text="Analisando DataModel..."
 local data=scan(); local body=HttpService:JSONEncode(data)
 local ok,res=pcall(function() return HttpService:RequestAsync({Url="http://127.0.0.1:8710/api/studio/manifest",Method="POST",Headers={["Content-Type"]="application/json"},Body=body}) end)
 if ok and res.Success then label.Text="Manifest enviado ao ARKHER.\n\nInstances: "..data.nodes.."\nScripts: "..#data.scripts.."\nRemotes: "..#data.remotes end
 else label.Text="Manifest local gerado em memoria.\n\nInstances: "..data.nodes.."\nScripts: "..#data.scripts.."\nRemotes: "..#data.remotes.."\n\nBackend: indisponivel ("..tostring(res and res.StatusCode or "sem resposta")..")" end
end
open.Click:Connect(run)
