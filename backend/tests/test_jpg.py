from backend.app.tools.jpeg import encode_jpeg
from backend.app.tools.jpg_cena import gerar_jpg
from backend.app.acervo.modelos import mixamo_nota


def test_jpeg_magic_and_size():
    rgb = bytes([40, 30, 20, 200, 180, 90] * (16 * 16 // 2))
    raw = encode_jpeg(16, 16, rgb, 80)
    assert raw[:2] == b"\xff\xd8"
    assert raw[-2:] == b"\xff\xd9"
    assert len(raw) > 80


def test_cena_jpg_b64():
    r = gerar_jpg("atelier noite", 7, 64, 48)
    assert r["arquivo"]["nome"].endswith(".jpg")
    import base64
    raw = base64.b64decode(r["arquivo"]["conteudo_b64"])
    assert raw[:2] == b"\xff\xd8"


def test_mixamo_sem_scrape():
    n = mixamo_nota()
    assert n["download"] is False
    assert "scrape" in n["message"].lower() or "não tem API" in n["message"] or "nao tem API" in n["message"].lower() or "API" in n["message"]
