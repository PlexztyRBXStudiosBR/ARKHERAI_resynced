"""Ferramentas do ARKHER — autorizadas pelo backend, validadas e auditadas.

Primeira versão (sem shell, sem controle remoto, sem instalação de programas):
  calc          — calculadora segura (AST, sem eval);
  file_read     — leitura de arquivos enviados pelo usuário (sandbox por usuário);
  text_analysis — análise de texto;
  data_export   — exportação dos dados do usuário;
  memory_query  — consulta à memória própria.
"""
from __future__ import annotations

import ast
import base64
import json
import re
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path

from backend.app import config
from backend.app.memory import service as memory_service
from backend.app.storage import db
from backend.app.tools import blender_gen, build_gen, generators, rbxlx_gen

MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_READ_CHARS = 200_000

TOOLS: dict[str, dict] = {
    "calc": {
        "id": "calc",
        "nome": "Calculadora segura",
        "descricao": "Avalia expressões aritméticas simples usando AST (nunca eval).",
        "permissoes": ["nenhuma_permissao_externa"],
        "confirmacao": False,
    },
    "file_read": {
        "id": "file_read",
        "nome": "Leitura de arquivos do usuário",
        "descricao": "Lê apenas arquivos que o próprio usuário enviou ao servidor (sandbox por usuário).",
        "permissoes": ["leitura_da_sandbox_do_usuario"],
        "confirmacao": True,
    },
    "text_analysis": {
        "id": "text_analysis",
        "nome": "Análise de texto",
        "descricao": "Contagens, palavras mais frequentes e estimativa de leitura.",
        "permissoes": ["nenhuma_permissao_externa"],
        "confirmacao": False,
    },
    "data_export": {
        "id": "data_export",
        "nome": "Exportação de dados",
        "descricao": "Exporta conversas e memórias do usuário em JSON.",
        "permissoes": ["leitura_dos_dados_do_usuario"],
        "confirmacao": True,
    },
    "memory_query": {
        "id": "memory_query",
        "nome": "Consulta à memória própria",
        "descricao": "Busca textual local nas memórias salvas com consentimento.",
        "permissoes": ["leitura_da_memoria_do_usuario"],
        "confirmacao": False,
    },
    "roblox_gen": {
        "id": "roblox_gen",
        "nome": "Gerador de scripts Roblox (Luau)",
        "descricao": "Gera scripts Luau prontos (leaderstats, salvamento, teleporte, dia/noite, checkpoint) para colar no Roblox Studio. Código gerado pelo projeto, revisado por você.",
        "permissoes": ["geracao_de_codigo_local"],
        "confirmacao": False,
    },
    "obj_gen": {
        "id": "obj_gen",
        "nome": "Gerador de terreno 3D (OBJ)",
        "descricao": "Gera um terreno heightmap em formato OBJ para importar no Blender ou na sua engine. Determinístico pela seed.",
        "permissoes": ["geracao_de_asset_local"],
        "confirmacao": False,
    },
    "anim_gen": {
        "id": "anim_gen",
        "nome": "Gerador de animação (keyframes)",
        "descricao": "Gera trilhas de keyframes procedurais (girar, flutuar, pulsar, vaivem, tremer) prontas para o animador do Arkher Studio. Determinístico pela seed.",
        "permissoes": ["geracao_de_animacao_local"],
        "confirmacao": False,
    },
    "blender_gen": {
        "id": "blender_gen",
        "nome": "Conector Blender (3D real)",
        "descricao": "Gera scripts Python do Blender (terreno, cena, personagem, animação e texturas 4K tileable). Com Blender no servidor, executa de verdade e devolve .glb/.png; sem Blender, entrega o .py para rodar no seu.",
        "permissoes": ["geracao_de_script_3d", "execucao_blender_local_se_instalado"],
        "confirmacao": True,
    },
    "rbxlx_gen": {
        "id": "rbxlx_gen",
        "nome": "Gerador de place nativo Roblox Studio (.rbxlx)",
        "descricao": "Gera um place pronto no formato XML oficial do Roblox Studio (obby, arena, base). Você baixa e abre direto no Studio — a cena já vem construída.",
        "permissoes": ["geracao_de_place_roblox"],
        "confirmacao": False,
    },
    "build_gen": {
        "id": "build_gen",
        "nome": "Construção ao vivo (pontes Roblox Studio + Blender)",
        "descricao": "Interpreta seu pedido em linguagem natural (sem lista fixa: torres, quartéis, casas, árvores, veículos, muros, heliponto…) e compõe a construção peça por peça. As pontes montam em tempo real dentro do Studio/Blender abertos; também entrega .rbxlx.",
        "permissoes": ["geracao_de_stream_de_construcao", "geracao_de_place_roblox", "modelagem_no_blender"],
        "confirmacao": False,
    },
    "ponte_instalar": {
        "id": "ponte_instalar",
        "nome": "Instalação das pontes (Studio + Blender)",
        "descricao": "Com sua permissão, libera o plugin do Roblox Studio e o addon do Blender para a ARKHER construir/modelar ao vivo nos programas abertos.",
        "permissoes": ["instalacao_assistida_da_ponte"],
        "confirmacao": True,
    },
}


class ToolError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_authorized(user_id: str, tool_id: str) -> bool:
    rows = db.query(
        "SELECT 1 FROM tool_auth WHERE user_id = ? AND tool_id = ?", (user_id, tool_id)
    )
    return bool(rows)


def authorize(user_id: str, tool_id: str) -> None:
    if tool_id not in TOOLS:
        raise ToolError("UNKNOWN_TOOL", "Ferramenta desconhecida.")
    db.execute(
        "INSERT OR REPLACE INTO tool_auth (user_id, tool_id, authorized_at) VALUES (?, ?, ?)",
        (user_id, tool_id, _now()),
    )


def revoke(user_id: str, tool_id: str) -> None:
    db.execute("DELETE FROM tool_auth WHERE user_id = ? AND tool_id = ?", (user_id, tool_id))


def history(user_id: str, limit: int = 100) -> list[dict]:
    rows = db.query(
        "SELECT tool_id, ok, arg_summary, ms, created_at FROM tool_log "
        "WHERE user_id = ? ORDER BY id DESC LIMIT ?",
        (user_id, limit),
    )
    return [dict(r) for r in rows]


def _audit(user_id: str, tool_id: str, ok: bool, arg_summary: str, ms: int) -> None:
    db.execute(
        "INSERT INTO tool_log (user_id, tool_id, ok, arg_summary, ms, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, tool_id, int(ok), arg_summary[:120], ms, _now()),
    )


# --------------------------------------------------------------- executores
_ALLOWED_NODES = (
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
    ast.USub, ast.UAdd,
)


def _calc(expr: str) -> dict:
    expr = expr.strip().replace(",", ".")
    if len(expr) > 200:
        raise ToolError("TOO_LONG", "Expressão longa demais.")
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        raise ToolError("INVALID_EXPR", "Expressão inválida.")
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise ToolError("FORBIDDEN_EXPR", "A expressão usa operadores não permitidos.")
    try:
        value = eval(compile(tree, "<calc>", "eval"), {"__builtins__": {}}, {})  # noqa: S307 — AST validado, sem nomes
    except ZeroDivisionError:
        raise ToolError("DIV_ZERO", "Divisão por zero.")
    except Exception:
        raise ToolError("INVALID_EXPR", "Não consegui avaliar a expressão.")
    return {"expressao": expr, "resultado": value}


def _text_analysis(text: str) -> dict:
    words = re.findall(r"\w+", text.lower())
    freq: dict[str, int] = {}
    for w in words:
        freq[w] = freq.get(w, 0) + 1
    top = sorted(freq.items(), key=lambda kv: -kv[1])[:10]
    return {
        "caracteres": len(text),
        "palavras": len(words),
        "linhas": text.count("\n") + 1,
        "palavras_unicas": len(freq),
        "mais_frequentes": [{"palavra": w, "vezes": n} for w, n in top],
        "tempo_leitura_min": round(len(words) / 200, 1),
    }


def uploads_dir(user_id: str) -> Path:
    d = config.DATA_DIR / "uploads" / user_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_upload(user_id: str, name: str, content_b64: str) -> dict:
    raw = base64.b64decode(content_b64, validate=True)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise ToolError("TOO_BIG", "Arquivo maior que 2 MB.")
    safe = re.sub(r"[^\w.\-]", "_", name)[:80] or "arquivo.txt"
    path = uploads_dir(user_id) / safe
    path.write_bytes(raw)
    return {"nome": safe, "bytes": len(raw)}


def _file_read(user_id: str, name: str) -> dict:
    base = uploads_dir(user_id).resolve()
    alvo = (base / name).resolve()
    if not str(alvo).startswith(str(base)) or not alvo.is_file():
        raise ToolError("NOT_FOUND", "Arquivo não encontrado na sua sandbox.")
    text = alvo.read_text(encoding="utf-8", errors="replace")[:MAX_READ_CHARS]
    return {"nome": name, "caracteres": len(text), "conteudo": text}


def run(user_id: str, tool_id: str, args: dict) -> dict:
    """Valida autorização, executa e registra a ação."""
    if tool_id not in TOOLS:
        raise ToolError("UNKNOWN_TOOL", "Ferramenta desconhecida.")
    if not is_authorized(user_id, tool_id):
        raise ToolError("NOT_AUTHORIZED", "Ferramenta sem autorização. Autorize na tela Ferramentas.")
    t0 = time.monotonic()
    try:
        if tool_id == "calc":
            result = _calc(str(args.get("expressao", "")))
        elif tool_id == "text_analysis":
            result = _text_analysis(str(args.get("texto", ""))[:20_000])
        elif tool_id == "file_read":
            result = _file_read(user_id, str(args.get("nome", "")))
        elif tool_id == "data_export":
            result = _data_export(user_id)
        elif tool_id == "memory_query":
            result = {"resultados": memory_service.search(user_id, str(args.get("q", "")))}
        elif tool_id == "roblox_gen":
            try:
                result = generators.gerar_roblox(str(args.get("tipo", "")))
            except ValueError as e:
                raise ToolError("INVALID_ARG", str(e))
        elif tool_id == "obj_gen":
            try:
                result = generators.gerar_terreno(args.get("seed"))
            except ValueError as e:
                raise ToolError("INVALID_ARG", str(e))
        elif tool_id == "anim_gen":
            try:
                result = generators.gerar_animacao(
                    str(args.get("tipo", "")),
                    args.get("seed"),
                    float(args.get("duracao", 2.0) or 2.0),
                )
            except ValueError as e:
                raise ToolError("INVALID_ARG", str(e))
        elif tool_id == "blender_gen":
            try:
                seed = int(args.get("seed", 42))
                cena = str(args.get("cena", ""))
                script = blender_gen.gerar_script(cena, seed)
            except ValueError as e:
                raise ToolError("INVALID_ARG", str(e))
            artefatos = blender_gen.executar(script, f"{cena}_seed{seed}")
            if artefatos is not None:
                result = {
                    "modo": "blender_real",
                    "descricao": f"A ARKHER executou o Blender de verdade ({', '.join(artefatos['itens'])}).",
                    "arquivo": artefatos,
                }
            else:
                result = {
                    "modo": "script_para_usuario",
                    "descricao": "O Blender não está instalado neste servidor. Segue o script pronto para rodar no seu Blender (ou instale o Blender no servidor e a ARKHER executa de verdade).",
                    "arquivo": {"nome": f"{cena}_seed{seed}_arkher.py", "conteudo": script},
                }
        elif tool_id == "rbxlx_gen":
            try:
                seed = int(args.get("seed", 42))
                result = rbxlx_gen.gerar_place(args.get("tipo", ""), seed)
            except ValueError as e:
                raise ToolError("INVALID_ARG", str(e))
        elif tool_id == "build_gen":
            try:
                tema = str(args.get("tema", ""))
                seed = int(args.get("seed", 42))
                build = build_gen.criar_build(user_id, tema, seed)
            except ValueError as e:
                raise ToolError("INVALID_ARG", str(e))
            xml = rbxlx_gen.renderizar_ops(build["ops"])
            nome_seguro = re.sub(r"[^a-z0-9]+", "_", build["tema"].lower()).strip("_")[:32] or "build"
            result = {
                "descricao": (
                    f"Construção '{build['tema']}' gerada (seed {build['seed']}, "
                    f"{len(build['ops'])} peças, build `{build['build_id']}`)."
                ),
                "como_usar": (
                    "Com uma ponte ARKHER conectada (Studio ou Blender), clique em "
                    "'Construir agora' e ela monta peça por peça no programa aberto. "
                    "Sem ponte? Baixe o .rbxlx anexo e abra direto no Studio."
                ),
                "arquivo": {"nome": f"arkher_{nome_seguro}_seed{build['seed']}.rbxlx", "conteudo": xml},
            }
        elif tool_id == "ponte_instalar":
            result = {
                "descricao": "Permissão registrada. As pontes estão liberadas para construir ao vivo.",
                "como_usar": (
                    "Roblox Studio: baixe o plugin em /api/build/plugin e salve em "
                    "%LOCALAPPDATA%/Roblox/Plugins/ArkherPonte.lua (ou arraste para o Studio).\n"
                    "Blender: baixe o addon em /api/build/plugin-blender e instale em "
                    "Edit → Preferences → Add-ons → Install.\n"
                    "Nos dois painéis, cole o endereço do servidor ARKHER e o seu token. "
                    "Depois é só pedir a construção no chat e clicar em 'Construir agora'."
                ),
            }
        else:
            raise ToolError("UNKNOWN_TOOL", "Ferramenta desconhecida.")
        _audit(user_id, tool_id, True, json.dumps(args, ensure_ascii=False), int((time.monotonic() - t0) * 1000))
        return result
    except ToolError as e:
        _audit(user_id, tool_id, False, json.dumps(args, ensure_ascii=False), int((time.monotonic() - t0) * 1000))
        raise e


def _data_export(user_id: str) -> dict:
    sessions = [dict(r) for r in db.query(
        "SELECT id, title, created_at, updated_at FROM sessions WHERE user_id = ?", (user_id,)
    )]
    for s in sessions:
        s["mensagens"] = [dict(r) for r in db.query(
            "SELECT role, content, kind, created_at FROM messages WHERE session_id = ? ORDER BY created_at",
            (s["id"],),
        )]
    return {
        "exportado_em": _now(),
        "conversas": sessions,
        "memorias": memory_service.export(user_id),
    }
