> ⚠️ DOCUMENTO HISTÓRICO — FORA DO DEPLOY.
> Este arquivo existe apenas para registrar o que foi removido do código antigo.
> Nenhuma linha do sistema antigo foi reaproveitada no runtime novo.
> Os nomes de serviços citados abaixo aparecem somente aqui, como registro histórico.

# Inventário de remoção — código legado do ARKHER (set/2026)

## O que o projeto antigo era
Um agregador de IAs de terceiros rodando 100% no navegador, com:
- catálogo de modelos externos e "vias grátis" de múltiplos provedores;
- pool/armazém de tokens e contas de terceiros (compartilhados via serviço de banco externo);
- rotação automática de chaves quando a cota de um provedor acabava ("low balance");
- fallback silencioso entre provedores ("se um modelo falhar eu troco para outro");
- VM Windows recorrente criada por workflow de CI com chave de rede privada (Tailscale),
  religada por cron a cada 5 horas, com agente remoto e acesso RDP;
- "DsOS": cliente de tela remota/sandbox remoto;
- "operários"/enxame de contas externas para tarefas automatizadas;
- scripts de publicação, empacotamento e telemetria que enviavam dados para fora.

## Arquivos removidos do runtime (apagados do repositório de trabalho)
`index.html` (antigo), `app.js`, `ui.js`, `freeai.js`, `pool.js`, `auth.js`,
`auth_social.js`, `sync.js`, `realtime.js`, `memoria.js`, `conhecimento.js`,
`neural.js`, `skills.js`, `respostas.js`, `websearch.js`, `compute.js`, `cotas.js`,
`core.js`, `vault.js`, `pilot.js`, `pwa.js`, `sw.js`, `kaggle.js`,
`dsos.js`, `dsos_client.js`, `dsos_core.py`, `rdp.js`,
`agent.py`, `hf_hub.py`, `gerar3d.py`, `telemetria.py`, `ws_min.py`,
`religa_kaggle.py`, `arkher_kaggle.ipynb`, `arkher_station_worker.py`,
`arkher_station.js`, `arkher_station_bridge.js`, `arkher_station_ui.js`,
`arkher_worker.js`, `arkher_operarios.js`, `arkher_ligar.js`, `arkher_pack.js`,
`arkher_publicar.js`, `arkher_task.js`, `arkher_dinamico.js`, `arkher_eval.js`,
`arkher_gamedev.js`, `arkher_guard.js`, `arkher_hud.js`, `arkher_doctor.py`,
`enxame.js`, `cerebro_ui.js`,
`prova.html`, `prova_frame.html`, `manifest.json` (antigo),
todos os `teste_*.js` e `teste_*.py` antigos,
`deploy/` antigo (systemd + env de exemplo antigo),
`.github/workflows/arkher.yml` (fábrica de VM com cron).

## Documentos antigos removidos (substituídos pela documentação nova)
`README.md` antigo, `COMO-USAR.txt`, `RECURSOS.txt`, `ENGINE.txt`,
`PUBLICAR.txt`, `ANDROID.txt`, `DSOS.txt`.

## O que foi preservado (identidade visual e conteúdo, não runtime)
- `icons/` — ícones/logo do ARKHER (identidade visual).
- `roblox/` — scripts Lua de conteúdo game dev do projeto (conteúdo, não runtime).

## Práticas do código antigo que o runtime novo NÃO reintroduz
1. Chamada direta do navegador a qualquer provedor de IA externo.
2. Armazenamento/rotação/captura de tokens de terceiros.
3. Fallback silencioso entre provedores.
4. Criação automatizada de VMs/PCs remotos para computação ou hospedagem.
5. Acesso remoto a máquinas (tela remota, agente, RDP, túnel privado).
6. Telemetria ou sincronização para serviços externos.
7. Qualquer script solto carregado por `index.html` fora do bundle único.
