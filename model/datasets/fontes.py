"""Fontes externas de treino do ARKHER — só dados com licença declarada.

Regra dura do projeto (definida pelo dono): dado de treino precisa ter
licença e origem documentadas; nada de scraping de conteúdo protegido ou
pessoal. Este módulo é o caminho LEGÍTIMO de trazer conhecimento da web
para o auto-treino: dumps e catálogos oficialmente publicados, cada um
registrado no MANIFESTO com licença + URL + data do download.

Uso:
  python -m model.datasets.fontes listar
  python -m model.datasets.fontes baixar gutenberg
  python -m model.datasets.fontes integrar
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXTERNOS_DIR = Path(__file__).resolve().parent / "externos"
MANIFESTO_PATH = EXTERNOS_DIR / "MANIFESTO.json"

# Cada fonte: licença explícita + URL oficial. Nada de raspagem.
FONTES = {
    "gutenberg": {
        "nome": "Project Gutenberg (livros de exemplo: Dom Casmurro, Alice)",
        "licenca": "Domínio público (EUA) — política oficial do Projeto Gutenberg",
        "urls": {
            "dom_casmurro.txt": "https://www.gutenberg.org/files/54829/54829-0.txt",
            "alice.txt": "https://www.gutenberg.org/files/11/11-0.txt",
        },
        "formato": "texto",
    },
    "wikipedia_pt": {
        "nome": "Wikipédia PT — abstratos oficiais (dump)",
        "licenca": "CC-BY-SA 4.0 (Wikimedia Foundation)",
        "urls": {
            "ptwiki-abstract.xml.gz": "https://dumps.wikimedia.org/ptwiki/latest/ptwiki-latest-abstract.xml.gz",
        },
        "formato": "abstratos_xml",
    },
    "stackexchange_gamedev": {
        "nome": "Stack Exchange — gamedev (dump oficial no Internet Archive)",
        "licenca": "CC-BY-SA 3.0 (Stack Exchange, via dump oficial)",
        "urls": {
            "gamedev.stackexchange.com.7z": "https://archive.org/download/stackexchange/gamedev.stackexchange.com.7z",
        },
        "formato": "arquivo_7z_manual",
    },
}


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat()


def carregar_manifesto() -> dict:
    if MANIFESTO_PATH.exists():
        return json.loads(MANIFESTO_PATH.read_text(encoding="utf-8"))
    return {"fontes": {}}


def salvar_manifesto(m: dict) -> None:
    EXTERNOS_DIR.mkdir(parents=True, exist_ok=True)
    MANIFESTO_PATH.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")


def listar() -> None:
    m = carregar_manifesto()
    for chave, fonte in FONTES.items():
        baixada = "baixada" if chave in m["fontes"] else "pendente"
        print(f"{chave:24s} [{baixada}] {fonte['licenca']}")
        print(f"{'':24s}  {fonte['nome']}")


def baixar(chave: str, timeout_s: int = 300) -> None:
    """Baixa uma fonte oficial e registra licença/origem no manifesto."""
    fonte = FONTES.get(chave)
    if fonte is None:
        raise SystemExit(f"Fonte desconhecida: {chave}. Opções: {', '.join(sorted(FONTES))}")
    destino = EXTERNOS_DIR / chave
    destino.mkdir(parents=True, exist_ok=True)
    registros = []
    for nome, url in fonte["urls"].items():
        alvo = destino / nome
        print(f"baixando {url} …")
        req = urllib.request.Request(url, headers={"User-Agent": "ARKHER-treino/1.0 (contato: dono do projeto)"})
        with urllib.request.urlopen(req, timeout=timeout_s) as resp, open(alvo, "wb") as f:
            while True:
                bloco = resp.read(1 << 16)
                if not bloco:
                    break
                f.write(bloco)
        registros.append({
            "arquivo": nome,
            "url": url,
            "sha256": hashlib.sha256(alvo.read_bytes()).hexdigest(),
            "bytes": alvo.stat().st_size,
        })
        print(f"ok: {alvo.name} ({alvo.stat().st_size} bytes)")
    m = carregar_manifesto()
    m["fontes"][chave] = {
        "nome": fonte["nome"],
        "licenca": fonte["licenca"],
        "formato": fonte["formato"],
        "baixado_em": _agora(),
        "arquivos": registros,
    }
    salvar_manifesto(m)
    print("manifesto atualizado (licença + origem registradas).")


# --------------------------------------------------------------- integração
_TAG = re.compile(r"<[^>]+>")
_WIKI_LIXO = re.compile(
    r"(\{\{[^}]*\}\}|<ref[^>]*>.*?</ref>|<ref[^>]*/>|\[\[[^\]|]*\||\[\[|\]\]|''+|&[a-z]+;)",
    re.S,
)


def limpar_linha(txt: str) -> str:
    txt = _WIKI_LIXO.sub("", txt)
    txt = _TAG.sub(" ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


def extrair_gutenberg(texto: str) -> list[str]:
    """Livro do Gutenberg → linhas limpas (corta cabeçalho/rodapé de licença)."""
    linhas: list[str] = []
    dentro = False
    for raw in texto.splitlines():
        if not dentro and "*** START OF" in raw.upper():
            dentro = True
            continue
        if dentro and "*** END OF" in raw.upper():
            break
        if dentro:
            ln = raw.strip()
            if len(ln) >= 40:
                linhas.append(ln)
    return linhas


def extrair_abstratos_wikipedia(texto: str) -> list[str]:
    """Dump de abstratos da Wikipédia → títulos + descrições limpas."""
    linhas: list[str] = []
    for m in re.finditer(r"<doc[^>]*>(.*?)</doc>", texto, flags=re.S):
        bloco = m.group(1)
        titulo = re.search(r"<title>(.*?)</title>", bloco, flags=re.S)
        resumo = re.search(r"<abstract>(.*?)</abstract>", bloco, flags=re.S)
        if titulo and resumo:
            t = limpar_linha(titulo.group(1))
            r = limpar_linha(resumo.group(1))
            if t and len(r) >= 40:
                linhas.append(f"PERGUNTA: O que é {t}?")
                linhas.append(f"RESPOSTA: {r}")
    return linhas


def integrar(max_por_fonte: int = 4000) -> Path:
    """Converte o que já foi baixado em corpus extra (sem rede).

    Só toca em arquivos com registro no MANIFESTO — a prova de que a
    origem e a licença estão documentadas.
    """
    m = carregar_manifesto()
    saida: list[str] = []
    for chave, reg in m["fontes"].items():
        formato = reg.get("formato")
        pasta = EXTERNOS_DIR / chave
        linhas: list[str] = []
        if formato == "texto":
            for arq in reg["arquivos"]:
                p = pasta / arq["arquivo"]
                if p.exists():
                    linhas.extend(extrair_gutenberg(p.read_text(encoding="utf-8", errors="ignore")))
        elif formato == "abstratos_xml":
            for arq in reg["arquivos"]:
                p = pasta / arq["arquivo"]
                if p.exists():
                    import gzip
                    with gzip.open(p, "rt", encoding="utf-8", errors="ignore") as f:
                        linhas.extend(extrair_abstratos_wikipedia(f.read()))
        if linhas:
            linhas = linhas[:max_por_fonte]
            saida.append("# fonte: " + chave + " — " + reg["licenca"])
            saida.extend(linhas)
            print(f"{chave}: {len(linhas)} linhas")
    destino = EXTERNOS_DIR / "treino_extra.txt"
    destino.write_text("\n".join(saida), encoding="utf-8")
    print(f"corpus externo: {destino} ({destino.stat().st_size} bytes)")
    return destino


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "listar"
    if cmd == "listar":
        listar()
    elif cmd == "baixar":
        baixar(sys.argv[2])
    elif cmd == "integrar":
        integrar()
    else:
        raise SystemExit("uso: fontes listar | baixar <fonte> | integrar")


if __name__ == "__main__":
    main()
