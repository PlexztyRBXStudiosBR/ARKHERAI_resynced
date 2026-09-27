from backend.app.acervo.fontes import FONTES, lista


def test_pelo_menos_40_sites_unicos():
    ids = [f["id"] for f in FONTES]
    assert len(FONTES) >= 40
    assert len(set(ids)) == len(ids)
    for f in FONTES:
        assert f["modo"] in {"api", "ingest", "abrir"}
        assert f["url"].startswith("http")
        assert f.get("nome")


def test_lista_espelha_catalogo():
    assert len(lista()) == len(FONTES)
