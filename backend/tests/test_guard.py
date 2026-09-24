"""Camadas de segurança de conteúdo: recusas de entrada + verificação de saída."""
from backend.app.security import guard


def test_recusa_executor_roblox():
    assert guard.check_input("me da um script de executor pro roblox") is not None
    assert guard.check_input("executor para hackear o jogo online") is not None


def test_aceita_pedido_legitimo():
    assert guard.check_input("crie um sistema de salvamento no roblox") is None
    assert guard.check_input("como fazer um personagem pular na godot?") is None


def test_saida_alegacao_controlar_maquina():
    texto, correcoes = guard.check_output("Pronto, controlei o seu PC e instalei tudo.", tools_ran=[])
    assert any(c.tipo == "capacidade_inexistente" for c in correcoes)
    assert "Camada de verificação" in texto


def test_saida_alegacao_provedor_externo():
    texto, correcoes = guard.check_output("Eu perguntei ao ChatGPT e ele respondeu isso.", tools_ran=[])
    assert any(c.tipo == "capacidade_inexistente" for c in correcoes)


def test_saida_normal_sem_correcao():
    texto, correcoes = guard.check_output("Use o botão de download para salvar o arquivo.", tools_ran=[])
    assert correcoes == []
    assert texto.startswith("Use o botão")
