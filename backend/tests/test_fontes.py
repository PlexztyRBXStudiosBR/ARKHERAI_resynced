"""Fontes externas de treino: licença documentada e extração limpa."""
from model.datasets import fontes


def test_toda_fonte_tem_licenca_e_url_oficial():
    for chave, fonte in fontes.FONTES.items():
        assert fonte["licenca"], f"{chave} sem licença documentada"
        assert fonte["urls"], f"{chave} sem URL oficial"
        for url in fonte["urls"].values():
            assert url.startswith("https://"), f"{chave} com origem insegura"


def test_limpar_linha_remove_marcacao_wiki():
    sujo = "'''Jogo eletrônico''' é uma [[interação]] {{ficha}} com<ref>x</ref> regras."
    limpo = fontes.limpar_linha(sujo)
    assert "[[" not in limpo and "{{" not in limpo and "<ref" not in limpo and "''" not in limpo
    assert "Jogo eletrônico é uma interação com regras." == limpo


def test_extrair_gutenberg_corta_cabecalho_rodape():
    texto = (
        "The Project Gutenberg eBook of X\n"
        "license blah blah\n"
        "*** START OF THE PROJECT GUTENBERG EBOOK X ***\n"
        "Era uma casa muito engraçada, não tinha teto não tinha nada.\n"
        "Curta\n"
        "Ninguém podia entrar nela, não, porque na casa não tinha chão.\n"
        "*** END OF THE PROJECT GUTENBERG EBOOK X ***\n"
        "license rodapé\n"
    )
    linhas = fontes.extrair_gutenberg(texto)
    assert len(linhas) == 2
    assert all("license" not in l for l in linhas)


def test_extrair_abstratos_formato_pergunta_resposta():
    xml = (
        "<feed>"
        "<doc><title>Motor de jogo</title>"
        "<abstract>Um motor de jogo é um conjunto de ferramentas que facilita"
        " a criação de jogos, renderização e física.</abstract></doc>"
        "<doc><title>Curto</title><abstract>pequeno</abstract></doc>"
        "</feed>"
    )
    linhas = fontes.extrair_abstratos_wikipedia(xml)
    # o segundo doc é descartado (resumo curto demais)
    assert linhas == [
        "PERGUNTA: O que é Motor de jogo?",
        "RESPOSTA: Um motor de jogo é um conjunto de ferramentas que facilita a criação de jogos, renderização e física.",
    ]


def test_integrar_somente_com_manifesto(tmp_path, monkeypatch):
    """Sem registro no manifesto (licença/origem), nada entra no corpus."""
    ext = tmp_path / "externos"
    ext.mkdir()
    monkeypatch.setattr(fontes, "EXTERNOS_DIR", ext)
    monkeypatch.setattr(fontes, "MANIFESTO_PATH", ext / "MANIFESTO.json")
    destino = fontes.integrar()
    assert destino.read_text(encoding="utf-8") == ""
