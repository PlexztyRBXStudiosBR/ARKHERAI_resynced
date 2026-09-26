from backend.app.acervo.convert import categoria, ingerir, pastas
from backend.app.workspace.service import ip_permitido


def test_ip_permitido_tailscale_e_lan():
    assert ip_permitido("100.64.1.8")
    assert ip_permitido("192.168.0.10")
    assert ip_permitido("10.0.0.2")
    assert ip_permitido("127.0.0.1")
    assert not ip_permitido("8.8.8.8")
    assert not ip_permitido("169.254.169.254")
    assert not ip_permitido("not-an-ip")


def test_workspace_rejeita_ip_publico(auth_client):
    r = auth_client.post(
        "/api/workspace",
        json={"name": "x", "tailscale_ip": "8.8.8.8", "username": "a", "password": "b"},
    )
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "BAD_IP"


def test_workspace_cria_e_lista(auth_client):
    r = auth_client.post(
        "/api/workspace",
        json={"name": "vm1", "tailscale_ip": "100.64.0.2", "username": "arkher", "password": "segredo"},
    )
    assert r.status_code == 200
    vm = r.json()["vm"]
    assert vm["agent_token"].startswith("agt_")
    assert "password" not in vm
    lista = auth_client.get("/api/workspace").json()["vms"]
    assert any(x["id"] == vm["id"] for x in lista)
    assert "password" not in lista[0]
    assert auth_client.delete(f"/api/workspace/{vm['id']}").json()["ok"]


def test_integrations_catalogo(auth_client):
    r = auth_client.get("/api/integrations")
    assert r.status_code == 200
    ids = {i["id"] for i in r.json()["integrations"]}
    for preciso in ("github", "blender", "roblox", "youtube", "google", "figma", "tailscale", "termux"):
        assert preciso in ids
    assert len(ids) >= 20
    auth_client.post("/api/integrations/github/authorize", json={"token": "ghp_teste"})
    after = {i["id"]: i for i in auth_client.get("/api/integrations").json()["integrations"]}
    assert after["github"]["authorized"] is True
    assert after["github"]["has_token"] is True
    # token nunca volta
    assert "token" not in after["github"] or after["github"].get("token") in (None, "")


def test_acervo_organiza_xml(tmp_path):
    root = tmp_path / "ArkherAITraining"
    (root / "mapas").mkdir(parents=True)
    xml = '<?xml version="1.0"?><roblox><Item class="Workspace"></Item></roblox>'
    (root / "mapas" / "arena_place.rbxlx").write_text(xml, encoding="utf-8")
    (root / "npc_char.rbxmx").write_text(xml, encoding="utf-8")
    res = ingerir(root)
    assert res["ok"]
    assert res["xml_rbxlx"] >= 1
    assert res["xml_rbxmx"] >= 1
    folders = pastas(root)
    assert any(folders["xml_rbxlx"].rglob("*.rbxlx"))
    assert any(folders["xml_rbxmx"].rglob("*.rbxmx"))
    assert categoria("arena_place") == "mapas"
    assert categoria("npc_char") == "personagens"


def test_acervo_nao_finge_binario(tmp_path):
    root = tmp_path / "ArkherAITraining"
    root.mkdir()
    (root / "jogo.rbxl").write_bytes(b"<notxml"[:0] + b"\x00binary-roblox")
    res = ingerir(root)
    assert res["ok"]
    rec = [a for a in res["arquivos"] if a["tipo"] == "rbxl"][0]
    assert rec.get("xml") is None
    assert rec["conversao"]["ok"] is False
