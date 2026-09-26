"""Abas fora do Roblox: Design, Pesquisa, Código, Pipeline.

Dão à ARKHER o resto da produção — briefing, fontes licenciadas,
ferramentas de código e o caminho até publicar — sem modelo de terceiro.
"""
from __future__ import annotations

import json
import re

from backend.app.tools import web_search


def _md(nome: str, corpo: str, descricao: str) -> dict:
    return {
        "descricao": descricao,
        "arquivo": {"nome": nome, "conteudo": corpo},
        "como_usar": "Use no chat, no Vault e no Workspace. Isto alimenta as outras abas.",
    }


def gerar_design(recipe: str, prompt: str, seed: int) -> dict:
    tema = (prompt or "jogo de ação cooperativo").strip()[:200]
    if recipe == "gdd":
        corpo = f"""# GDD — {tema}
seed {seed}

## Visão (1 frase)
Um jogo onde o jogador {tema.lower()}, com sessão de 15–25 min e loop claro.

## Pilares (máx 3)
1. Legibilidade — o jogador lê o perigo em <0,5 s.
2. Agência — toda morte ensina uma regra, nunca um RNG invisível.
3. Ritmo — 90 s de tensão, 20 s de respiro.

## Fantasia
Quem o jogador quer *ser* e o que ele quer *fazer* nos primeiros 30 s.

## Loop nuclear
objetivo curto → obstáculo lido → decisão → recompensa visível → novo objetivo.

## Sistemas (o que a ARKHER deve gerar depois)
- Places / Models / Luau conforme o loop
- HUD (aba UI) + áudio (aba Áudio)
- Netcode se for multiplayer
- Pipeline de ship no final da semana

## Fora de escopo (v1)
Não promete mundo aberto, crafting infinito nem live-ops.
"""
        return _md(f"arkher_gdd_{seed}.md", corpo, f"GDD de '{tema}' — briefing para todas as abas.")
    if recipe == "loop":
        corpo = f"""# Loop — {tema}

```
[Hub] --aceita contrato--> [Run 8-12 min] --extrai--> [Upgrade] --volta--> [Hub]
```

- Moeda: só dropa no extrair, nunca no chão do run (evita farm AFK).
- Falha: perde 50% da run, guarda 1 relic.
- Daily: 1 contrato extra, não battle-pass.
"""
        return _md(f"arkher_loop_{seed}.md", corpo, "Loop nuclear + economia curta.")
    if recipe == "economia":
        corpo = f"""# Economia — {tema}

| Item | Drop | Sink | Teto |
| --- | --- | --- | --- |
| Soft | 8–14 / run | upgrade 10, 25, 60 | 500 |
| Relic | 15% boss | slot 3 | 3 |
| Cosmético | 0 no PvE | loja (premium só se você quiser) | — |

Regra: nenhum sink exige grind de 2 h. ARKHER gera a loja na aba UI e o DataStore na aba Luau.
"""
        return _md(f"arkher_economia_{seed}.md", corpo, "Tabela de economia jogável.")
    # pilares
    corpo = f"""# Pilares — {tema}

1. **Ler** — silhueta, cor, som. Sem tutorial de 4 min.
2. **Decidir** — 2 opções boas, 1 péssima visível.
3. **Pagar** — custo de stamina/ balas / posição, nunca de paciência.

Anti-pilares (proibido na v1): FOMO, gacha, daily que pune quem trabalha.
"""
    return _md(f"arkher_pilares_{seed}.md", corpo, "Pilares e anti-pilares para não diluir o jogo.")


def gerar_pesquisa(recipe: str, prompt: str) -> dict:
    q = (prompt or "procedural terrain game design").strip()[:200]
    fonte = None if recipe == "brief" else recipe
    if fonte == "wikipedia":
        fonte = "wikipedia"
    elif fonte == "archive":
        fonte = "internet_archive"
    elif fonte == "docs":
        fonte = "roblox_docs"
    else:
        fonte = None
    try:
        bruto = web_search.pesquisar(q, fonte, "pt")
    except Exception as e:  # noqa: BLE001
        bruto = {"ok": False, "code": "FONTE_INDISPONIVEL", "message": str(e), "consulta": q}
    linhas = [f"# Pesquisa ARKHER — {q}", "", f"receita: {recipe}", ""]
    if not bruto.get("ok"):
        linhas += [
            "Fonte indisponível (honesto, sem inventar).",
            f"código: {bruto.get('code')}",
            f"detalhe: {bruto.get('message')}",
            "",
            "A ARKHER segue com o que já sabe no corpus próprio. Tente de novo com rede.",
        ]
    else:
        linhas.append(str(bruto.get("atribuicao") or ""))
        fontes = bruto.get("fontes") or [bruto]
        for bloco in fontes:
            if not isinstance(bloco, dict):
                continue
            linhas.append(f"\n## {bloco.get('fonte', recipe)}")
            for item in (bloco.get("resultados") or [])[:6]:
                linhas.append(f"- [{item.get('titulo')}]({item.get('url')}) — {item.get('resumo', '')[:220]}")
                if item.get("licenca"):
                    linhas.append(f"  licença: {item['licenca']}")
    corpo = "\n".join(linhas) + "\n"
    return _md(
        f"arkher_pesquisa_{re.sub(r'[^a-z0-9]+', '_', q.lower())[:32]}.md",
        corpo,
        "Pesquisa em fontes abertas/licenciadas, com atribuição. Nada de scrape escondido.",
    )


def gerar_codigo(recipe: str, prompt: str, seed: int) -> dict:
    tema = (prompt or "export pack").strip()[:120]
    if recipe == "python":
        codigo = f'''#!/usr/bin/env python3
"""ARKHER helper — {tema} (seed {seed}). Stdlib only."""
from __future__ import annotations
import argparse, json, hashlib
from pathlib import Path

def sha(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pasta", type=Path)
    a = ap.parse_args()
    out = [{{"nome": p.name, "sha256": sha(p), "bytes": p.stat().st_size}}
           for p in sorted(a.pasta.rglob("*")) if p.is_file()]
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
'''
        return {
            "descricao": f"Ferramenta Python para '{tema}' — manifesto SHA-256 de uma pasta.",
            "arquivo": {"nome": f"arkher_tool_{seed}.py", "conteudo": codigo},
            "como_usar": "Rode no Workspace/Termux: python arkher_tool_SEED.py pasta/",
        }
    if recipe == "shader":
        codigo = f"""// ARKHER — shader toon barato (Godot/Unity-like GLSL). Tema: {tema}
shader_type spatial;
uniform vec4 cor : source_color = vec4(0.2, 0.7, 0.4, 1.0);
uniform float faixas : hint_range(2.0, 6.0) = 3.0;
void fragment() {{
    float l = clamp(dot(NORMAL, vec3(0.3, 0.8, 0.4)), 0.0, 1.0);
    l = floor(l * faixas) / faixas;
    ALBEDO = cor.rgb * (0.35 + 0.65 * l);
}}
"""
        return {
            "descricao": "Shader toon de 1 pass — serve Godot/Unity/Blender.",
            "arquivo": {"nome": f"arkher_toon_{seed}.gdshader", "conteudo": codigo},
            "como_usar": "Cole no Godot Spatial ou adapte no Blender.",
        }
    if recipe == "json":
        corpo = json.dumps(
            {
                "arkher": 1,
                "tema": tema,
                "seed": seed,
                "sistemas": ["hud", "save", "audio", "vfx"],
                "build": {"versao": "0.1.0", "canais": ["dev", "qa", "live"]},
            },
            ensure_ascii=False,
            indent=2,
        )
        return {
            "descricao": "Schema JSON do projeto — as outras abas leem estes IDs.",
            "arquivo": {"nome": f"arkher_projeto_{seed}.json", "conteudo": corpo},
            "como_usar": "Fonte da verdade do jogo, fora da engine.",
        }
    # ci
    codigo = f"""# ARKHER CI — {tema}
name: arkher-check
on: [push]
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python -m py_compile $(git ls-files '*.py')
      - run: test -f README.md
"""
    return {
        "descricao": "Workflow CI mínimo (sintaxe Python + README). Sem modelo externo.",
        "arquivo": {"nome": "arkher-check.yml", "conteudo": codigo},
        "como_usar": "Cola em .github/workflows/ no seu GitHub (integração autorizada).",
    }


def gerar_pipeline(recipe: str, prompt: str, seed: int) -> dict:
    tema = (prompt or "build da semana").strip()[:120]
    if recipe == "ship":
        corpo = f"""# Checklist de ship — {tema}

- [ ] GDD fechado (aba Design)
- [ ] Place jogável 8 min (aba Places)
- [ ] Save + remotes validados (aba Luau / Netcode)
- [ ] HUD + 1 som (abas UI / Áudio)
- [ ] 1 textura tileable (aba Materiais)
- [ ] Vault com hash novo (sem treino repetido)
- [ ] Playtest 3 pessoas, 1 folha de QA
- [ ] Build nomeada `v0.1.{seed}` no Workspace
- [ ] NÃO publicar sem a sua confirmação
"""
        return _md(f"arkher_ship_{seed}.md", corpo, "Checklist de ship — o que um time médio esquece.")
    if recipe == "export":
        corpo = f"""# Pacote de export — {tema}

```
dist/{seed}/
  place.rbxlx
  models/*.rbxmx
  scripts/*.lua
  art/*.png
  blender/*.py
  gdd.md
  MANIFEST.json   # sha256 de cada arquivo
```

No Workspace: `python arkher_tool_{seed}.py dist/{seed}`
"""
        return _md(f"arkher_export_{seed}.md", corpo, "Árvore de export pronta para zipar.")
    if recipe == "qa":
        corpo = f"""# Folha de QA — {tema}

| # | Caso | Esperado | Passou |
| --- | --- | --- | --- |
| 1 | Entra no place | spawn visível, sem void | |
| 2 | Morre | respawn no checkpoint | |
| 3 | Save | reloga com o mesmo inventário | |
| 4 | Remote spam | servidor ignora >8/s | |
| 5 | Mobile | botões não cobrem o golpe | |
| 6 | Áudio | mute master zera Sfx+Musica | |

3 testers, 20 min cada. Anote build `{seed}`.
"""
        return _md(f"arkher_qa_{seed}.md", corpo, "Casos de QA objetivos — sem feeling.")
    corpo = f"""# Notas de versão — {tema}

## v0.1.{seed}
- Loop nuclear jogável
- Save + HUD
- 1 place, 1 model, 1 textura

## Próximo
- 2º place
- VFX do golpe
- Mixer de áudio

Sem live-ops nesta versão.
"""
    return _md(f"arkher_changelog_{seed}.md", corpo, "Changelog curto para o próximo ciclo da ARKHER.")
