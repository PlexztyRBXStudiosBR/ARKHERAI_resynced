"""Camadas de segurança de conteúdo do ARKHER.

1. `check_input`  — recusa honesta de categorias proibidas (ilegais, +18,
   trapaças/exploits de jogos online, malware). Fora disso, nada de censura.
2. `check_output` — camada extra de correção de resposta:
   - verifica aritmética declarada no texto e corrige erros;
   - aponta alegações de ações não executadas neste turno (ex.: "acessei a internet");
   - impede atribuição da resposta a terceiros.

As regras são explícitas e auditáveis; nada aqui depende de serviço externo.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

REFUSAL = (
    "Não posso ajudar com isso. A ARKHER não produz conteúdo ilegal, conteúdo adulto, "
    "trapaças ou exploits para jogos online, nem código para prejudicar outras pessoas "
    "ou sistemas. Para todo o resto, é só pedir."
)

# --------------------------------------------------------------------- entrada
_INPUT_RULES: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"(?i)\b(executor|cheat|cheats|aimbot|wallhack|auto\s?clicker|injet(?:ar|or|a)|exploit|"
            r"script\s+de\s+(?:menu|mod|hack)|hackear|hack\s+(?:de|do|para))\b.{0,60}\b(roblox|jogo|game|online)\b"
            r"|\b(roblox|jogo|game)\b.{0,60}\b(executor|cheat|aimbot|wallhack|exploit|injet(?:ar|or))\b"
        ),
        "cheat",
    ),
    (
        re.compile(r"(?i)\b(malware|ransomware|keylogger|stealer|phishing|trojan|roubar\s+(?:contas?|senhas?))\b"),
        "malware",
    ),
    (
        re.compile(
            r"(?i)\b(porn(?:o|ografia)?|sexo\s+expl[ií]cito|nudes?|conte[uú]do\s+(?:adulto|sexual|er[oó]tico))\b"
        ),
        "adulto",
    ),
    (
        re.compile(r"(?i)(fabricar|construir|montar)\s+(?:uma\s+)?(bomba|arma\s+de\s+fogo|explosivo)"),
        "ilegal",
    ),
    (
        re.compile(r"(?i)(sintetizar|produzir|fabricar)\s+(?:metanfetamina|drogas?\s+(?:ilegais?|sint[eé]ticas?))"),
        "ilegal",
    ),
]


def check_input(text: str) -> str | None:
    """Retorna mensagem de recusa ou None se a entrada for aceitável."""
    for pat, _categoria in _INPUT_RULES:
        if pat.search(text):
            return REFUSAL
    return None


# ---------------------------------------------------------------------- saída
_ARITH = re.compile(r"(-?\d+(?:[.,]\d+)?)\s*([+\-*/x×])\s*(-?\d+(?:[.,]\d+)?)\s*[=é]\s*(-?\d+(?:[.,]\d+)?)")

_FALSE_CLAIMS = [
    (re.compile(r"(?i)\b(acessei|consultei|pesquisei)\s+(?:a\s+)?internet\b"), "consultou a internet"),
    (re.compile(r"(?i)\bexecutei\s+(?:o\s+|um\s+)?(?:comando|c[oó]digo|script)\b"), "executou código"),
    (re.compile(r"(?i)\bli\s+(?:o\s+|um\s+)?arquivo\s+no\s+seu\s+(?:pc|computador)\b"), "leu arquivo local"),
    (re.compile(r"(?i)\b(enviei|subi|publiquei)\s+(?:o\s+)?arquivo\b"), "enviou arquivo"),
]


@dataclass
class Correction:
    tipo: str
    nota: str


def _num(s: str) -> float:
    return float(s.replace(",", "."))


def check_output(text: str, tools_ran: list[str]) -> tuple[str, list[Correction]]:
    """Revisa a resposta do modelo. Retorna (texto corrigido, correções aplicadas)."""
    corrections: list[Correction] = []

    # 1) aritmética: corrige resultados errados declarados no texto
    def fix(match: re.Match[str]) -> str:
        a, op, b, dado = match.group(1), match.group(2), match.group(3), match.group(4)
        try:
            fa, fb, fd = _num(a), _num(b), _num(dado)
        except ValueError:
            return match.group(0)
        if op in "+":
            real = fa + fb
        elif op == "-":
            real = fa - fb
        elif op in "*/x×":
            if op == "/":
                if fb == 0:
                    return match.group(0)
                real = fa / fb
            else:
                real = fa * fb
        else:
            return match.group(0)
        if abs(real - fd) > max(1e-9, abs(real) * 1e-6):
            fmt = ("%g" % real) if real != int(real) else str(int(real))
            corrections.append(
                Correction("aritmetica", f"Correção aritmética: {a} {op} {b} = {fmt} (estava {dado}).")
            )
            return match.group(0).replace(dado, fmt, 1)
        return match.group(0)

    text = _ARITH.sub(fix, text)

    # 2) alegações de ações que não aconteceram neste turno
    for pat, desc in _FALSE_CLAIMS:
        if pat.search(text):
            if not tools_ran:
                corrections.append(
                    Correction(
                        "acao_nao_executada",
                        f"Verificação: a resposta dizia ter {desc}, mas nenhuma ferramenta foi executada neste turno.",
                    )
                )

    # 3) atribuição a terceiros: a resposta é sempre da ARKHER
    if re.search(r"(?i)\bfui\s+(?:criada?|treinada?|feita?)\s+por\s+(?:outra|uma)\s+(?:empresa|ia|modelo)\b", text):
        corrections.append(Correction("atribuicao", "A ARKHER é o modelo próprio do projeto; a atribuição a terceiros foi removida."))
        text = re.sub(r"(?i)\bfui\s+(?:criada?|treinada?|feita?)\s+por\s+(?:outra|uma)\s+(?:empresa|ia|modelo)\b", "sou a ARKHER AI, modelo próprio do projeto ARKHER", text)

    if corrections:
        notas = "\n".join(f"- {c.nota}" for c in corrections)
        text = f"{text.rstrip()}\n\n_Camada de verificação do ARKHER:_\n{notas}"
    return text, corrections
