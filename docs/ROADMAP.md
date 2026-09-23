# Roadmap honesto do ARKHER AI

## Pronto nesta reconstrução
- Frontend novo (bundle único, responsivo, PWA instalável no celular).
- Backend próprio com auth local, SSE, rate limit e estados honestos.
- ARKHER-1 mini treinado de verdade no dataset semente (checkpoint demo).
- Memória com consentimento, ferramentas auditadas, camadas de segurança.
- Pipeline de treinamento completo e reproduzível.

## Próximos passos aprovados pela arquitetura atual
1. **Qualidade do modelo**: crescer dataset autorizado (textos autorais de game dev,
   código comentado, QA de engines) e hardware — mesmo pipeline, mesmo contrato.
2. **Continuar treinamento do checkpoint atual** (retomada) conforme chegam dados novos.
3. **Retrieval maior**: indexar mais blocos de conhecimento do projeto para o
   ARKHER-1 responder com base neles (busca textual local, já implementada).
4. **Visão/3D como ferramentas nativas**: quando existirem, serão ferramentas
   autorizadas e auditadas (como as atuais), nunca serviços externos embutidos.
5. **App instalável**: o site já é PWA; um APK pode embalar o mesmo site
   (decisão futura), mantinando a regra de falar só com o backend próprio.

## Ideias avaliadas e RECUSADAS neste projeto (com motivo)
| Ideia | Decisão | Motivo |
| --- | --- | --- |
| Usar runners de CI como "PCs de treino/servidor" | ❌ recusada | Viola os termos do serviço de CI; compute instável e não supervisionado. |
| Enxame de contas externas ("operários") para treinar/avaliar | ❌ recusada | Viola termos de serviços de terceiros; dados sem licença. |
| Raspar sites e transcrições de vídeo em massa para auto-treino | ❌ recusada | Direitos autorais e política do dataset; substituída por dados autorais/sintéticos. |
| A IA controlar máquinas reais (instalar programas, acesso remoto, túneis) | ❌ recusada | Superfície de risco inaceitável; o projeto nasceu removendo exatamente isso. |
| Armazenar pesos/conversas em hospedagens de arquivo de terceiros | ❌ recusada | Dados do usuário ficam em armazenamento local controlado pelo operador. |
| Trapaças/exploits para jogos online (ex.: executores) | ❌ recusada | Prejudica outros jogadores e viola termos das plataformas; recusa implementada. |
| Fallback silencioso para IA externa quando o modelo falha | ❌ recusada | O sistema informa o estado real em vez de fingir. |

## Fase 2 planejada: conectores nativos de ferramentas (caminho aprovado)
A potência por ferramentas — a ideia central do projeto — entra pela porta segura:

1. **Conector Blender**: quando houver modelo base maduro, o backend conversa com o
   Blender rodando na MÁQUINA DO USUÁRIO via API oficial, gerando scripts Python que o
   usuário revisa e executa com confirmação. Nada de controle remoto escondido.
2. **Conector Roblox Studio**: exportação de módulos Luau e assets gerados pela ARKHER
   para o projeto do usuário, com revisão humana antes de publicar.
3. **Conector de animação**: geração de blocos de keyframes/dados de animação em
   formatos abertos para uso em ferramentas do usuário.
4. **Sinal de uso**: o feedback 👍/👎 (já implementado) alimenta os ciclos de treino.

Esses conectores são o substituto legítimo de "controlar VMs": a ARKHER ganha
capacidade real de produção mantendo o usuário no controle e dentro dos termos
das ferramentas.

## Ideias adiadas (viáveis só com base madura)
- **Ambiente virtual isolado** para a IA experimentar com segurança: exige primeiro um
  modelo muito mais capaz e sandbox dedicado; hoje não há base para isso.
- **Conteúdo multimodal** (imagem/3D/textura): o runtime atual é texto; a arquitetura
  de ferramentas permite adicionar geradores nativos no futuro, um a um, testados.
- **Treino contínuo passivo**: só com dataset licenciado e servidor dedicado;
  o mecanismo de etapas já existe e roda sob confirmação do usuário.
