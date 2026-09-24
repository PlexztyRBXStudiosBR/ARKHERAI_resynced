"""Testes da pesquisa web — parsing/roteamento sem rede (fixtures)."""
from __future__ import annotations

import pytest

from backend.app.tools import web_search


def _fixture_http(monkeypatch, mapa: dict[str, dict]) -> None:
    def fake(url: str, timeout: float = 12.0) -> dict:
        for chave, payload in mapa.items():
            if chave in url:
                return payload
        raise AssertionError(f"URL inesperada: {url}")

    monkeypatch.setattr(web_search, "_http_json", fake)


def test_wikipedia_parsing(monkeypatch):
    _fixture_http(monkeypatch, {
        "pt.wikipedia.org": {
            "query": {"search": [
                {"title": "Motor de jogo", "snippet": "Um <b>motor</b> de jogo..."},
            ]}
        },
    })
    r = web_search.pesquisar("motor de jogo", fonte="wikipedia")
    assert r["ok"] and r["fonte"] == "wikipedia"
    assert r["resultados"][0]["url"].startswith("https://pt.wikipedia.org/wiki/")
    assert "<b>" not in r["resultados"][0]["resumo"]
    assert "CC BY-SA" in r["atribuicao"]


def test_internet_archive_parsing(monkeypatch):
    _fixture_http(monkeypatch, {
        "archive.org": {
            "response": {"docs": [
                {"identifier": "item1", "title": "Livro aberto",
                 "description": ["desc <i>a</i>"], "licenseurl": "https://creativecommons.org/licenses/by/4.0/"},
            ]}
        },
    })
    r = web_search.pesquisar("livro", fonte="internet_archive")
    assert r["ok"] and r["resultados"][0]["url"] == "https://archive.org/details/item1"
    assert r["resultados"][0]["licenca"].startswith("https://creativecommons.org")


def test_roblox_docs_indice_e_ranking(monkeypatch):
    web_search._docs_cache.update({"ts": 0.0, "caminhos": []})
    _fixture_http(monkeypatch, {
        "api.github.com": {"tree": [
            {"path": "content/en-us/reference/engine/classes/Terrain.md", "type": "blob"},
            {"path": "content/en-us/reference/engine/classes/Part.md", "type": "blob"},
            {"path": "content/en-us/roblox/icons.md", "type": "blob"},
            {"path": "README.md", "type": "blob"},
        ]},
    })
    r = web_search.pesquisar("terrain", fonte="roblox_docs")
    assert r["ok"] and r["docs_index"] == 3
    assert r["resultados"][0]["titulo"] == "Terrain"
    assert r["resultados"][0]["url"] == "https://create.roblox.com/docs/reference/engine/classes/Terrain"
    assert "CC-BY-4.0" in r["resultados"][0]["licenca"]
    # segunda chamada usa cache (sem nova URL github)
    r2 = web_search.pesquisar("part", fonte="roblox_docs")
    assert r2["resultados"][0]["titulo"] == "Part"


def test_youtube_sem_chave_eh_honesto(monkeypatch):
    monkeypatch.delenv("ARKHER_YT_KEY", raising=False)
    r = web_search.pesquisar("tutorial", fonte="youtube")
    assert r["ok"] is False and r["code"] == "SEM_CHAVE_YOUTUBE"


def test_fonte_desconhecida_e_consulta_curta():
    with pytest.raises(ValueError):
        web_search.pesquisar("algo valido", fonte="fonte_nao_existe")
    with pytest.raises(ValueError):
        web_search.pesquisar("ab")


def test_modo_combinado_registra_falhas(monkeypatch):
    web_search._docs_cache.update({"ts": 0.0, "caminhos": []})

    def fake(url: str, timeout: float = 12.0) -> dict:
        if "wikipedia" in url:
            return {"query": {"search": [{"title": "T", "snippet": "s"}]}}
        raise RuntimeError("sem rede nesta fonte")

    monkeypatch.setattr(web_search, "_http_json", fake)
    r = web_search.pesquisar("teste combinado")
    assert r["ok"] is True
    fontes_ok = [f["fonte"] for f in r["fontes"]]
    assert "wikipedia" in fontes_ok
    assert {f["fonte"] for f in r["falhas"]} == {"internet_archive", "roblox_docs"}
