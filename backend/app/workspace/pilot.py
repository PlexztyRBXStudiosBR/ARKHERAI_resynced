"""Chat de piloto: o usuário manda a ARKHER fazer X no PC da VM.

Só jobs permitidos (abrir Studio/Blender, print, importar, converter,
digitar, clicar, sync). Sem shell aberto.
"""
from __future__ import annotations

import re
import unicodedata

from backend.app.chat import composer
from backend.app.studio import kits
from backend.app.workspace import service as ws


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", (t or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def interpretar(mensagem: str) -> list[dict]:
    n = _norm(mensagem)
    jobs: list[dict] = []
    if re.search(r"\b(abre|abrir|abre o|abrir o|abre a)\b.*\b(studio|roblox)\b", n) or n.strip() in ("studio", "roblox studio"):
        jobs.append({"kind": "open_app", "args": {"app": "studio"}})
    if re.search(r"\b(abre|abrir)\b.*\bblender\b", n) or n.strip() == "blender":
        jobs.append({"kind": "open_app", "args": {"app": "blender"}})
    if re.search(r"\b(print|screenshot|captura|tela)\b", n):
        jobs.append({"kind": "screenshot", "args": {}})
    if re.search(r"\b(lista|ls|arquivos)\b", n):
        jobs.append({"kind": "ls", "args": {}})
    if re.search(r"\b(importa|abre o place|abrir place|abre o mapa)\b", n):
        m = re.search(r"([\\w.\\-]+\\.(rbxlx|rbxmx))", mensagem)
        jobs.append({"kind": "import_place", "args": {"path": m.group(1) if m else ""}})
    mt = re.search(r"digita(?:r)?\s+(.+)$", n)
    if mt:
        jobs.append({"kind": "type", "args": {"text": mt.group(1)[:200]}})
    mc = re.search(r"clica(?:r)?\s+(\d+)\s+(\d+)", n)
    if mc:
        jobs.append({"kind": "click", "args": {"x": int(mc.group(1)), "y": int(mc.group(2))}})
    if re.search(r"\b(converte|converter)\b", n) and re.search(r"\b(rbxl|rbxm)\b", n):
        jobs.append({"kind": "convert_rbx", "args": {"src": ""}})
    if re.search(r"\b(instala|instalar|baixa|baixar)\b.*\b(studio|roblox)\b", n):
        jobs.append({"kind": "install_app", "args": {"app": "studio"}})
    if re.search(r"\b(instala|instalar|baixa|baixar)\b.*\bblender\b", n):
        jobs.append({"kind": "install_app", "args": {"app": "blender"}})
    return jobs


def piloto(user_id: str, vm_id: str, mensagem: str) -> dict:
    mensagem = (mensagem or "").strip()
    if not mensagem:
        return {"ok": False, "reply": "Manda o comando: abre o Studio, print, digita …, clica X Y, gera um obby e importa."}
    if ws.obter(user_id, vm_id) is None:
        raise ws.WorkspaceError("NOT_FOUND", "PC virtual não encontrado.")

    jobs = interpretar(mensagem)
    resultados = []
    for j in jobs:
        try:
            resultados.append({"job": j, "result": ws.job(user_id, vm_id, j["kind"], j["args"])})
        except ws.WorkspaceError as e:
            resultados.append({"job": j, "result": {"ok": False, "code": e.code, "message": e.message}})

    # geração + envio ao PC (crie/gera/monta)
    n = _norm(mensagem)
    gerado = None
    if re.search(r"\b(crie|cria|gerar|gera|monta|fazer|faz)\b", n):
        tab, rec = "places", "obby"
        if "arena" in n:
            rec = "arena"
        elif "base" in n or "quartel" in n:
            rec = "base"
        elif "jeep" in n or "jipe" in n:
            tab, rec = "models", "jeep"
        elif "espada" in n or "sword" in n:
            tab, rec = "models", "sword"
        elif "textura" in n:
            tab, rec = "materiais", "pedra"
        elif "blender" in n or "personagem" in n:
            tab, rec = "blender", "personagem"
        elif "hud" in n or "ui" in n:
            tab, rec = "ui", "hud"
        elif "jogo inteiro" in n or "game completo" in n:
            tab, rec = "places", "jogo"
        try:
            gerado = kits.gerar(tab, rec, 42, mensagem)
            arq = gerado.get("arquivo") or {}
            if arq.get("nome") and (arq.get("conteudo") or arq.get("conteudo_b64")):
                sync = ws.job(
                    user_id,
                    vm_id,
                    "sync_file",
                    {"nome": arq["nome"], "conteudo": arq.get("conteudo") or "", "conteudo_b64": arq.get("conteudo_b64") or ""},
                )
                resultados.append({"job": {"kind": "sync_file"}, "result": sync})
                path = (sync or {}).get("path")
                if path and str(arq["nome"]).endswith((".rbxlx", ".rbxmx")):
                    resultados.append({"job": {"kind": "import_place"}, "result": ws.job(user_id, vm_id, "import_place", {"path": path})})
        except Exception as e:  # noqa: BLE001 — piloto devolve erro honesto
            resultados.append({"job": {"kind": "gerar"}, "result": {"ok": False, "message": str(e)}})

    n2 = _norm(mensagem)
    ciclo_res = None
    if re.search(r"\b(analisa|analisar|ingere|ciclo|pack|acervo)\b", n2):
        from backend.app.acervo import ciclo as ciclo_mod

        ciclo_res = ciclo_mod.rodar(user_id=user_id)
        par = ciclo_res.get("parametros") or {}
        linhas_c = [
            f"Pack: vistos={ciclo_res.get('analise', {}).get('vistos')} novos={ciclo_res.get('analise', {}).get('novos')} "
            f"pulados={ciclo_res.get('analise', {}).get('pulados_hash')} gigantes(100MB)={ciclo_res.get('analise', {}).get('gigantes_100mb')}.",
            f"Parâmetros agora: {par.get('params_agora'):,} ({par.get('nome')}, gen {par.get('gen_atual')}, {par.get('pct')}%). "
            f"Próximo: {par.get('proximo_nome')} ~{par.get('params_proximo'):,}.",
        ]
        if not jobs and gerado is None:
            return {"ok": True, "reply": "\n".join(linhas_c), "actions": [], "gerado": ciclo_res}

    if not jobs and gerado is None:
        reply = composer.responder(mensagem)
        reply += (
            "\n\nNo PC: **abre o Studio**, **abre o Blender**, **instala o Studio**, **instala o Blender**, "
            "**print**, **lista arquivos**, **digita …**, **clica X Y**, **analisa o pack**, **gera um obby e importa**."
        )
        return {"ok": True, "reply": reply, "actions": [], "gerado": None}

    linhas = ["Fiz no seu PC (jobs permitidos):"]
    for r in resultados:
        kind = (r["job"] or {}).get("kind")
        ok = (r["result"] or {}).get("ok", True)
        msg = (r["result"] or {}).get("message") or (r["result"] or {}).get("path") or ""
        linhas.append(f"- `{kind}`: {'ok' if ok else 'falhou'} {msg}".strip())
    if gerado:
        linhas.append(gerado.get("descricao") or "artefato gerado")
    if ciclo_res:
        par = ciclo_res.get("parametros") or {}
        linhas.append(
            f"Parâmetros: {par.get('params_agora'):,} agora → próximo {par.get('params_proximo'):,} "
            f"({par.get('proximo_nome')})."
        )
    return {"ok": True, "reply": "\n".join(linhas), "actions": resultados, "gerado": gerado or ciclo_res}
