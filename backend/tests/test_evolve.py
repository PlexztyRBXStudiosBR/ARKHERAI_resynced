from model.training import evolve


def test_evolve_nao_repete(tmp_path, monkeypatch):
    monkeypatch.setattr(evolve, "SEEN", tmp_path / "seen.json")
    monkeypatch.setattr(evolve, "CORPUS", tmp_path / "evolve.txt")
    d = tmp_path / "treino"
    d.mkdir()
    (d / "a.rbxlx").write_text("PLACE A", encoding="utf-8")
    monkeypatch.setattr(evolve, "TREINOS", [d])
    assert evolve.main() == 0
    n1 = (tmp_path / "evolve.txt").read_text(encoding="utf-8")
    assert "PLACE A" in n1
    # segunda passagem: mesma amostra, não duplica
    assert evolve.main() == 0
    n2 = (tmp_path / "evolve.txt").read_text(encoding="utf-8")
    assert n2.count("PLACE A") == n1.count("PLACE A")
