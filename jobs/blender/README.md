# Fila de geração 3D da ARKHER

Coloque aqui os scripts `.py` que a ARKHER gerou no chat (`/blender terreno|cena|personagem|animacao [seed]`,
ou pedindo em linguagem natural: "crie uma animação com textura no Blender").

Depois execute o nó de render na máquina que tiver Blender (seu PC, Kaggle, Colab):

```bash
python workers/render/render_node.py            # roda tudo que está aqui
python workers/render/render_node.py --zip      # e compacta os artefatos
```

Saída: `.glb` (3D real), `.png` (render) e, para `animacao`, a sequência de
quadros + GLB com keyframes. Nada é executado sem você rodar o comando.
