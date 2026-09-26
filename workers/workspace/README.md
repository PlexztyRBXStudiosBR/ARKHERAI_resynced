# Workspace — PC virtual (Windows App) + DsOS

Olhos e mãos do protótipo ArkherAI (`/screen`, `/input`, `/app`, `/guiready`,
`/frame`). **Sem** `/infer`, Shap-E, Puter, HF no chat, **sem** `/exec` aberto.

Um processo só na **8765** (agente + DsOS). Dois prints (8765+8766) travam.

## Erro que gerava “sem frame”

O agente antigo devolve `img` (data URL) e captura com PowerShell **`-STA`** +
`VirtualScreen` + arquivo. O nosso pedia só `b64` e dumpava JPEG no stdout
sem `-STA` → online (health) e tela vazia.

## Na VM (Windows App / sessão desbloqueada)

1. No site: cadastre IP Tailscale `100.x`, usuário, senha. Guarde o `agt_`.
2. Baixe o **agente** no Workspace.
3. **Dentro da sessão do Windows App** (não serviço, não lock screen):

```powershell
$env:ARKHER_AGENT_TOKEN = "agt_…"
python arkher_agent.py
```

4. **Tela ao vivo**. Toque: curto = clique, longo = direito, arrasta = drag.
5. **HUD** = você dirige Studio/Blender (setas, ESC, TAB, teclado). A IA não clica.

`dsos_core.py` é a porta 8766 do desenho antigo. Não rode junto com o agent.

Trabalhos do piloto (chat ao lado, HUD desligado): abrir Studio/Blender, print,
importar place, converter XML, digitar, clicar.
