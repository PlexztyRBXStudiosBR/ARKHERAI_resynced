# Viewport local da ARKHER

Executa no Termux sem Roblox Studio:

```bash
python tools/render_acervo.py \
  /storage/emulated/0/ArkherAITraining/_arkher/convertidos \
  --out /storage/emulated/0/ArkherAITraining/_arkher/rendered
```

Para um arquivo:

```bash
python tools/rbx_viewport.py jogo.rbxlx --out rendered
```

Saídas:

```text
jogo.svg   # imagem vetorial estrutural
jogo.html  # viewport no navegador + Explorer
jogo.json  # nós, paths, classes, posição, tamanho, cor e material
```

O renderizador não precisa de Pillow ou GPU. Ele faz uma vista top-down
ortográfica de Parts/Models e mostra tooltips com o caminho completo. É uma
aproximação para treinamento e indexação, não o renderer proprietário do
Roblox: scripts não são executados, física/iluminação/shaders/meshes complexos
não são reproduzidos fielmente. O Studio continua sendo a validação final.

As imagens SVG/HTML e o JSON podem ser enviados pelo backend ARKHER como
referência multimodal/estrutural. O corpus de treino deve guardar somente
projetos e assets com permissão/licença.
