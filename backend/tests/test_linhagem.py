from model.training import linhagem


def test_formula_ancora_no_mini():
    assert linhagem.params_pela_pct(20) == 4_000_000
    assert linhagem.params_pela_pct(30) == 8_000_000
    assert linhagem.params_pela_pct(10) == 2_000_000
    assert linhagem.params_pela_pct(40) == 16_000_000


def test_rung_18_pct_ainda_e_mini():
    r = linhagem.rung_por_pct(18)
    assert r["gen"] == 2
    assert r["nome"] == "ARKHER-1 mini"
    assert r["n_layers"] == 4
    assert r["d_model"] == 256


def test_rung_25_pct_sobe_midi():
    r = linhagem.rung_por_pct(25)
    assert r["gen"] == 3
    assert r["n_layers"] == 8
    assert r["d_model"] == 256  # mesma largura: dá para copiar blocos do mini


def test_estimativa_mini_perto_de_4m():
    n = linhagem.estimar_parametros(3072, 160, 4, 256, 1024)
    assert 3_800_000 < n < 4_200_000


def test_promover_so_quando_pct_passa_a_geracao():
    assert linhagem.deve_promover(18, 2) is False
    assert linhagem.deve_promover(25, 2) is True
    assert linhagem.deve_promover(25, 3) is False
    assert linhagem.deve_promover(100, 10) is False


def test_copia_compativel_nao_estoura_bloco_novo():
    class T:
        def __init__(self, shape, val):
            self.shape = shape
            self.val = val

        def detach(self):
            return self

        def clone(self):
            return T(self.shape, self.val)

    src = {"blocks.0.w": T((2, 2), 1), "tok": T((3,), 7)}
    dst = {"blocks.0.w": T((2, 2), 0), "blocks.4.w": T((2, 2), 9), "tok": T((3,), 0)}
    n = linhagem.copiar_state_compativel(src, dst)
    assert n == 2
    assert dst["blocks.0.w"].val == 1
    assert dst["blocks.4.w"].val == 9  # camada nova do aluno


def test_plano_tem_proximo():
    p = linhagem.plano(pct=18, gen_atual=2)
    assert p["promover"] is False
    assert p["atual"]["gen"] == 2
    assert p["proximo"]["gen"] == 3
    assert p["params_agora_formula"] == linhagem.params_pela_pct(18)
    p2 = linhagem.plano(pct=22, gen_atual=2)
    assert p2["promover"] is True
