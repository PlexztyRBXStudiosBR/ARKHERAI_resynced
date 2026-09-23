# ARKHER-1 mini — arquitetura

Modelo de linguagem próprio do projeto ARKHER, escrito do zero.

| Item | Valor |
| --- | --- |
| Família | Transformer decoder-only (atenção causal) |
| Camadas | 4 |
| Cabeças de atenção | 4 |
| d_model | 256 |
| d_ff | 1024 |
| Janela de contexto | 160 tokens |
| Vocabulário | 3.072 tokens (BPE próprio `bpe_v1`) |
| Parâmetros | ~3,98 M (embeddings amarradas) |
| Dispositivo alvo | CPU por padrão (CUDA/Metal se disponíveis) |
| Ativação | GELU, normalização pré-LayerNorm |
| Posição | Embeddings posicionais aprendidas |

## Estado honesto (v0.1.0-gamedev)
Este checkpoint é um **modelo pequeno especializado em game dev**, treinado em CPU no
dataset semente do próprio projeto (textos autorais de jogos/3D/animação/Roblox +
aritmética sintética, ~89 mil tokens). Ele prova o pipeline completo — tokenizer,
treino, checkpoint, inferência, streaming e cancelamento — e responde bem aos temas
do corpus. **Ainda não é um modelo conversacional amplo.** O estado é reportado como
`experimental` nos endpoints de status e na interface.

## Limites aplicados pelo runtime
- Entrada máxima: 140 tokens; saída máxima: 224 tokens (configurável em `config.yaml`).
- Timeout de geração: 120 s, com cancelamento cooperativo a cada token.
- Nenhum download de pesos: só carrega checkpoint local versionado.
