# Workspace — PC virtual da ARKHER

Inspirado no protótipo [ArkherAI](https://github.com/PlexztyRBXStudiosBR/ArkherAI)
(`agent.py`, DsOS, Tailscale). **Sem modelos de IA de terceiro.** O chat
continua sendo a ARKHER própria; o agente só opera o *seu* PC.

## No PC / VM (Windows recomendado p/ Studio)

1. Instale Tailscale e anote o IP `100.x.x.x`.
2. Copie esta pasta para a VM.
3. Rode, com o token que o site mostra **uma vez** ao criar o PC:

```powershell
$env:ARKHER_AGENT_TOKEN = "agt_…"
python workers/workspace/agent.py
```

4. No site, aba **Workspace**: nome, IP Tailscale, usuário Windows, senha.
5. **Testar conexão** → deve ficar *online*.
6. **Auto-logon** aplica `AutoAdminLogon` nesta VM (precisa de admin). Depois
   de um reboot, a sessão gráfica abre sozinha para o Studio/Blender.

Trabalhos permitidos (não é shell aberto): print da tela, abrir Studio/Blender/VS Code,
converter rbxl→rbxlx se `rbx-util` existir, importar place, rodar script Blender,
sincronizar arquivo gerado no chat.

## No celular (acervo)

```bash
python tools/roblox_dataset_ingest.py /storage/emulated/0/ArkherAITraining --once
```

XML vai para `_arkher/xml/rbxlx/<categoria>/` e `_arkher/xml/rbxmx/<categoria>/`.
A ARKHER lê esses XML, manda ao Studio do Workspace (com sua permissão) e cria
**duas versões**: a sua e a de treino (amostra nova; hash já visto não treina de novo).
