# Linhagem ARKHER — o modelo antigo ensina o novo

Não se copia IA de terceiro. O que avança a geração é o **pack** (XML, print da
VM, análise do jogo) passando no ciclo, não datacenter.

## Fórmula

```
params(pct) = 4_000_000 × 2^((pct − 20) / 10)
```

Mini atual (gen 2, ~20%) ≈ **4 M**. Cada **+10%** do produto = geração nova e
**dobra** os parâmetros.

| % produto | gen | nome | params alvo | o que muda |
|---:|---:|---|---:|---|
| 0–10 | 1 | nano | 2 M | |
| 10–20 | 2 | mini | 4 M | **você está aqui** |
| 20–30 | 3 | midi | 8 M | +4 camadas, mesma largura (copia blocos do mini) |
| 30–40 | 4 | ARKHER-1 | 16 M | +8 camadas |
| 40–50 | 5 | wide | 32 M | alarga; professor só destila |
| … | … | … | … | |
| 90–100 | 10 | ARKHER-4 | ~1 B | só depois do pack inteiro |

## Como treina

1. SHA-256 de cada amostra (XML, Luau, print, seed). Visto → **pula**.
2. Se a % cruzou o degrau: nasce o aluno, o checkpoint anterior é o **professor**
   (copia tensor de mesmo shape + KL nos logits).
3. Se não cruzou: retoma o mesmo modelo, só com amostra nova.

Código: `model/training/linhagem.py`, `evolve.py`, `train.py --gen --teacher`.
Cérebro no site mostra a escada ao vivo (`GET /api/cerebro/linhagem`).
