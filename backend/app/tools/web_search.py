"""Pesquisa na web — apenas fontes abertas/licenciadas, com atribuição.

A ARKHER pesquisa de verdade para ajudar a criar jogos, mas nunca esconde a
origem nem inventa resultado. Fontes suportadas:

- ``wikipedia``        : API pública da Wikipedia (conteúdo CC BY-SA 4.0).
- ``internet_archive`` : API pública do Internet Archive (licença por item).
- ``roblox_docs``      : documentação OFICIAL do Roblox via o repositório
                         público ``Roblox/creator-docs`` (licença CC-BY-4.0).
- ``youtube``          : somente com chave própria do usuário (``ARKHER_YT_KEY``).
                         Sem chave, devolve erro honesto — nunca scraping.

Sem rede disponível o erro é honesto (código ``FONTE_INDISPONIVEL``): a IA
prefere dizer que não conseguiu a inventar resposta.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
import urllib.request

TIMEOUT_S = 12.0
_USER_AGENT = "ArkherAI/0.1 (pesquisa educacional; https://github.com/PlexztyRBXStudiosBR/ARKHERAI_resynced)"

FONTES = ("wikipedia", "internet_archive", "roblox_docs", "youtube")

# cache do índice da documentação oficial do Roblox (árvore do repositório)
_docs_cache: dict[str, object] = {"ts": 0.0, "caminhos": []}
_DOCS_TTL_S = 24 * 3600
_HTML_TAG = re.compile(r"<[^>]+>")


def _http_json(url: str, timeout: float = TIMEOUT_S) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def _limpa_html(texto: str) -> str:
    return _HTML_TAG.sub("", texto or "").replace("\n", " ").strip()


# ------------------------------------------------------------------ wikipedia
def _pesquisa_wikipedia(consulta: str, idioma: str) -> dict:
    lang = (idioma or "pt").split("-")[0].strip().lower() or "pt"
    url = (
        f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search"
        f"&srsearch={urllib.parse.quote(consulta)}&srlimit=6&format=json"
    )
    dados = _http_json(url)
    resultados = []
    for item in dados.get("query", {}).get("search", []):
        titulo = str(item.get("title", "")).replace(" ", "_")
        resultados.append({
            "titulo": item.get("title", ""),
            "url": f"https://{lang}.wikipedia.org/wiki/{urllib.parse.quote(titulo)}",
            "resumo": _limpa_html(str(item.get("snippet", "")))[:300],
            "licenca": "CC BY-SA 4.0",
        })
    return {
        "ok": True,
        "fonte": "wikipedia",
        "idioma": lang,
        "consulta": consulta,
        "resultados": resultados,
        "atribuicao": "Wikipedia (CC BY-SA 4.0) — cite a fonte ao reutilizar.",
    }


# ---------------------------------------------------------- internet archive
def _pesquisa_internet_archive(consulta: str) -> dict:
    params = urllib.parse.urlencode({
        "q": consulta,
        "fl[]": ["identifier", "title", "description", "licenseurl", "mediatype"],
        "rows": 6,
        "output": "json",
    }, doseq=True)
    dados = _http_json(f"https://archive.org/advancedsearch.php?{params}")
    resultados = []
    for doc in dados.get("response", {}).get("docs", []):
        desc = doc.get("description", "")
        if isinstance(desc, list):
            desc = " ".join(str(d) for d in desc)
        resultados.append({
            "titulo": doc.get("title", doc.get("identifier", "")),
            "url": f"https://archive.org/details/{doc.get('identifier', '')}",
            "resumo": _limpa_html(str(desc))[:300],
            "licenca": doc.get("licenseurl") or "verificar no item",
        })
    return {
        "ok": True,
        "fonte": "internet_archive",
        "consulta": consulta,
        "resultados": resultados,
        "atribuicao": "Internet Archive — cada item informa a própria licença.",
    }


# --------------------------------------------------------------- roblox docs
def _indice_roblox_docs() -> list[str]:
    agora = time.time()
    if agora - float(_docs_cache["ts"]) < _DOCS_TTL_S and _docs_cache["caminhos"]:
        return list(_docs_cache["caminhos"])  # type: ignore[arg-type]
    dados = _http_json(
        "https://api.github.com/repos/Roblox/creator-docs/git/trees/main?recursive=1",
        timeout=20.0,
    )
    caminhos = [
        item["path"]
        for item in dados.get("tree", [])
        if item.get("type") == "blob"
        and str(item.get("path", "")).startswith("content/en-us/")
        and str(item.get("path", "")).endswith(".md")
    ]
    _docs_cache.update({"ts": agora, "caminhos": caminhos})
    return caminhos


def _pesquisa_roblox_docs(consulta: str) -> dict:
    termos = [t for t in re.split(r"\W+", consulta.lower()) if len(t) >= 3][:6]
    if not termos:
        raise ValueError("Consulta muito curta para pesquisar na documentação.")
    caminhos = _indice_roblox_docs()
    pontuados: list[tuple[int, str]] = []
    for caminho in caminhos:
        base = caminho.rsplit("/", 1)[-1][:-3].lower()
        partes = set(re.split(r"[-_/]", base))
        score = 0
        for termo in termos:
            if termo == base:
                score += 6
            elif termo in partes:
                score += 3
            elif termo in base:
                score += 1
        if score > 0:
            pontuados.append((score, caminho))
    pontuados.sort(key=lambda x: (-x[0], x[1]))
    resultados = []
    for _, caminho in pontuados[:6]:
        relativo = caminho[len("content/en-us/"):-3]
        nome = caminho.rsplit("/", 1)[-1][:-3]
        resultados.append({
            "titulo": nome,
            "url": f"https://create.roblox.com/docs/{relativo}",
            "resumo": f"Documentação oficial do Roblox: {relativo}",
            "licenca": "CC-BY-4.0 (Roblox creator-docs)",
        })
    return {
        "ok": True,
        "fonte": "roblox_docs",
        "consulta": consulta,
        "resultados": resultados,
        "docs_index": len(caminhos),
        "atribuicao": "Roblox creator-docs (CC-BY-4.0) — documentação oficial.",
    }


# ------------------------------------------------------------------- youtube
def _pesquisa_youtube(consulta: str) -> dict:
    chave = os.environ.get("ARKHER_YT_KEY", "").strip()
    if not chave:
        return {
            "ok": False,
            "fonte": "youtube",
            "code": "SEM_CHAVE_YOUTUBE",
            "message": (
                "Pesquisa no YouTube exige a sua própria chave da API "
                "(variável ARKHER_YT_KEY no backend). Sem chave a ARKHER não "
                "faz scraping — as outras fontes (Wikipedia, Internet Archive, "
                "documentação oficial do Roblox) continuam liberadas."
            ),
        }
    url = (
        "https://www.googleapis.com/youtube/v3/search?part=snippet&type=video"
        f"&maxResults=6&q={urllib.parse.quote(consulta)}&key={chave}"
    )
    dados = _http_json(url)
    resultados = []
    for item in dados.get("items", []):
        vid = item.get("id", {}).get("videoId", "")
        resultados.append({
            "titulo": _limpa_html(str(item.get("snippet", {}).get("title", ""))),
            "url": f"https://www.youtube.com/watch?v={vid}",
            "resumo": _limpa_html(str(item.get("snippet", {}).get("description", "")))[:300],
            "licenca": "vídeo de terceiros — direitos do canal",
        })
    return {
        "ok": True,
        "fonte": "youtube",
        "consulta": consulta,
        "resultados": resultados,
        "atribuicao": "YouTube Data API v3 — respeite os direitos de cada canal.",
    }


# -------------------------------------------------------------------- pública
def pesquisar(consulta: str, fonte: str | None = None, idioma: str = "pt") -> dict:
    """Pesquisa real em fontes abertas. ``fonte=None`` tenta as 3 abertas."""
    consulta = (consulta or "").strip()
    if len(consulta) < 3:
        raise ValueError("Consulta precisa de pelo menos 3 caracteres.")
    fonte_norm = (fonte or "").strip().lower()
    if fonte_norm and fonte_norm not in FONTES:
        raise ValueError(f"Fonte desconhecida. Opções: {', '.join(FONTES)}")

    if fonte_norm == "wikipedia":
        return _pesquisa_wikipedia(consulta, idioma)
    if fonte_norm == "internet_archive":
        return _pesquisa_internet_archive(consulta)
    if fonte_norm == "roblox_docs":
        return _pesquisa_roblox_docs(consulta)
    if fonte_norm == "youtube":
        return _pesquisa_youtube(consulta)

    # modo combinado: tenta as fontes abertas, registra falhas honestamente
    saida = {
        "ok": True,
        "consulta": consulta,
        "fontes": [],
        "falhas": [],
        "atribuicao": "Resultados de fontes abertas; cada um informa a licença.",
    }
    for nome, fn in (
        ("wikipedia", lambda: _pesquisa_wikipedia(consulta, idioma)),
        ("internet_archive", lambda: _pesquisa_internet_archive(consulta)),
        ("roblox_docs", lambda: _pesquisa_roblox_docs(consulta)),
    ):
        try:
            saida["fontes"].append(fn())
        except Exception as e:  # noqa: BLE001 — falha de rede é honesta
            saida["falhas"].append({"fonte": nome, "erro": f"FONTE_INDISPONIVEL: {e}"})
    if not saida["fontes"]:
        return {
            "ok": False,
            "code": "SEM_REDE",
            "message": (
                "Nenhuma fonte aberta respondeu agora. Verifique a internet do "
                "backend e tente de novo — a ARKHER não inventa resultados."
            ),
            "falhas": saida["falhas"],
        }
    return saida
