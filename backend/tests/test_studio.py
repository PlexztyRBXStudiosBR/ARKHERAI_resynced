from xml.etree import ElementTree as ET

from backend.app.studio import kits
from backend.app.workspace.pilot import interpretar


def test_catalogo_tem_abas_gamedev():
    ids = {c["id"] for c in kits.CATALOGO}
    assert len(ids) >= 13
    for preciso in ("places", "models", "luau", "terrain", "animacao", "materiais", "lighting", "ui", "netcode", "vfx", "blender"):
        assert preciso in ids


def test_gera_place_xml():
    res = kits.gerar("places", "obby", 3)
    xml = res["arquivo"]["conteudo"]
    raiz = ET.fromstring(xml)
    assert raiz.tag == "roblox"
    assert "Workspace" in [it.get("class") for it in raiz.iter("Item")]


def test_gera_model_rbxmx():
    res = kits.gerar("models", "jeep", 1)
    assert res["arquivo"]["nome"].endswith(".rbxmx")
    raiz = ET.fromstring(res["arquivo"]["conteudo"])
    classes = [it.get("class") for it in raiz.iter("Item")]
    assert "Model" in classes and classes.count("Part") >= 5


def test_gera_luau_e_ui():
    lua = kits.gerar("luau", "remotes", 1)
    assert "OnServerEvent" in lua["arquivo"]["conteudo"]
    ui = kits.gerar("ui", "hud", 1)
    assert "ScreenGui" in ui["arquivo"]["conteudo"]


def test_gera_textura_png():
    tex = kits.gerar("materiais", "pedra", 7)
    assert tex["arquivo"]["nome"].endswith(".png")
    assert tex["arquivo"]["conteudo_b64"]


def test_studio_api(auth_client):
    r = auth_client.get("/api/studio/catalog")
    assert r.status_code == 200
    assert len(r.json()["tabs"]) >= 13
    g = auth_client.post("/api/studio/generate", json={"tab": "luau", "recipe": "combate", "seed": 2})
    assert g.status_code == 200
    assert "TakeDamage" in g.json()["result"]["arquivo"]["conteudo"]
    bad = auth_client.post("/api/studio/generate", json={"tab": "luau", "recipe": "hack", "seed": 1})
    assert bad.status_code == 400


def test_abas_gerais_nao_roblox():
    gdd = kits.gerar("design", "gdd", 4, "stealth coop")
    assert gdd["arquivo"]["nome"].endswith(".md")
    assert "Pilares" in gdd["arquivo"]["conteudo"]
    py = kits.gerar("codigo", "python", 4, "pack")
    assert py["arquivo"]["nome"].endswith(".py")
    assert "sha256" in py["arquivo"]["conteudo"]
    ship = kits.gerar("pipeline", "ship", 4, "alpha")
    assert "Checklist" in ship["arquivo"]["conteudo"]
    pesquisa = kits.gerar("pesquisa", "brief", 1, "noise")
    assert pesquisa["arquivo"]["conteudo"].startswith("# Pesquisa")


def test_piloto_interpreta_comandos():
    jobs = interpretar("abre o Roblox Studio")
    assert jobs and jobs[0]["kind"] == "open_app"
    jobs = interpretar("digita Hello")
    assert jobs[-1]["kind"] == "type"
    jobs = interpretar("clica 100 200")
    assert jobs[-1]["args"] == {"x": 100, "y": 200}
    jobs = interpretar("instala o Roblox Studio")
    assert any(j["kind"] == "install_app" and j["args"]["app"] == "studio" for j in jobs)
    jobs = interpretar("instala o blender")
    assert any(j["kind"] == "install_app" and j["args"]["app"] == "blender" for j in jobs)
