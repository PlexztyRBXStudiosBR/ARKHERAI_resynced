"""Camada especialista própria da ARKHER — responde qualquer pergunta.

Não usa provedor externo de IA. Combina:
- recuperação local no corpus do projeto;
- pacotes de especialidade (Roblox, Blender, engines, produção);
- geradores determinísticos quando o pedido é criar.

Quando o modelo próprio está carregado, o chat ainda pode continuá-lo;
quando não está, esta camada responde sozinha — nunca manda a pessoa
'instalar a ponte' no lugar de uma resposta.
"""
from __future__ import annotations

import re
import unicodedata

from backend.app.chat import knowledge

_WORD = re.compile(r"\w{3,}", re.U)


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", (t or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c))


IDENTIDADE = (
    "Sou a **ARKHER AI**, inteligência própria do projeto ARKHER — núcleo, "
    "tokenizer, memória e ferramentas da casa. Especialidade: game dev de ponta, "
    "com ênfase em Roblox Studio, Blender, engines, netcode, arte 3D, animação, "
    "texturas e produção. Respondo qualquer assunto; quando o pedido for criar, "
    "eu gero o artefato **aqui no chat** (place, mesh, textura, animação, script). "
    "Integrações são permissões de fontes externas; o Workspace é o seu PC virtual. "
    "Eu não sou um agregador de modelos de terceiros."
)


def overlap(message: str, tokens: set[str]) -> int:
    msg = set(t.lower() for t in _WORD.findall(message))
    return len(msg & tokens)


def _conhecimento(message: str) -> str | None:
    hits = knowledge.retrieve(message, limit=3)
    if not hits:
        return None
    best = hits[0]
    q_tok = best.get("q_tokens") or set()
    if overlap(message, q_tok) >= 3 or len(best["a"]) < 900:
        # resposta completa do bloco — não o prefixo de 16 palavras
        corpo = best["a"].strip()
        extras = [h["a"].strip() for h in hits[1:] if h["a"].strip() != corpo]
        if extras:
            corpo += "\n\n—\n\n" + extras[0]
        return corpo
    return None


def _matematica(message: str) -> str | None:
    t = message.strip()
    if re.fullmatch(r"[\d\s\+\-\*/\(\)\.,]+", t) and any(c in t for c in "+-*/"):
        try:
            from backend.app.tools.registry import _calc

            r = _calc(t)
            return f"{r['expressao']} = **{r['resultado']}**"
        except Exception:
            return None
    m = re.search(r"(?:quanto e|calcule|calcula)\s+(.+)$", _norm(message))
    if m:
        try:
            from backend.app.tools.registry import _calc

            r = _calc(m.group(1))
            return f"{r['expressao']} = **{r['resultado']}**"
        except Exception:
            return None
    return None


def _especialista(message: str) -> str:
    n = _norm(message)
    if re.search(r"\b(quem e voce|quem es|o que e a arkher|sua identidade)\b", n):
        return IDENTIDADE
    if re.search(r"\b(oi|ola|hey|eae|fala|bom dia|boa tarde|boa noite)\b", n) and len(n) < 40:
        return (
            IDENTIDADE
            + "\n\nPode perguntar qualquer coisa — código, design, Roblox, Blender, "
            "produção, matemática, ou peça para eu **criar** (place, personagem, "
            "terreno, animação, textura). Eu gero no próprio chat."
        )

    blocos: list[str] = []
    hits = knowledge.retrieve(message, limit=2)
    if hits:
        blocos.append(hits[0]["a"].strip())

    if re.search(r"\b(roblox|luau|studio|datasto|leaderstat|obby|remoteevent)\b", n):
        blocos.append(_pacote_roblox(message, n))
    elif re.search(r"\b(blender|mesh|shader|uv|rig|armature|gltf|glb)\b", n):
        blocos.append(_pacote_blender(message, n))
    elif re.search(r"\b(netcode|lag|replicat|snapshot|prediction|ggpo)\b", n):
        blocos.append(_pacote_netcode(n))
    elif re.search(r"\b(textura|albedo|normal map|roughness|pbr)\b", n):
        blocos.append(_pacote_textura(n))
    elif re.search(r"\b(animacao|keyframe|tween|animator)\b", n):
        blocos.append(_pacote_animacao(n))
    elif re.search(r"\b(treino|treinar|checkpoint|dataset|evolu)\b", n):
        blocos.append(
            "O treino da ARKHER é próprio e incremental: o modelo anterior ensina o "
            "próximo **somente com amostras novas** (hash SHA-256; nada de treino "
            "repetido). Operários do Hugging Face, se autorizados, só geram/filtram "
            "dados licenciados — os pesos continuam ARKHER. Acompanhe na aba Cérebro."
        )

    if not blocos:
        blocos.append(_resposta_aberta(message, n))

    # dedup simples
    vistos: set[str] = set()
    out: list[str] = []
    for b in blocos:
        k = b[:80]
        if k in vistos:
            continue
        vistos.add(k)
        out.append(b)
    return "\n\n".join(out)


def _pacote_roblox(message: str, n: str) -> str:
    return (
        "Como especialista Roblox, eu trato o Studio como produção de verdade: "
        "StreamingEnabled, atributos em vez de ValueObject solto, módulos com "
        "contrato, RemoteEvents com validação no servidor, DataStore com "
        "retry/backoff e schema versionado, AnimationController/Animator com "
        "prioridade, e places em XML (`.rbxlx`/`.rbxmx`) para diff e treino.\n\n"
        f"Pedido: {message.strip()}\n\n"
        "Se quiser o artefato, peça **crie** (obby, arena, base, sistema de save, "
        "teleporte, dia/noite). Eu gero o arquivo no chat — versão sua + versão "
        "de treino arquivada, sem repetir amostra já treinada. Para aplicar no "
        "Studio aberto do seu PC, conecte o Workspace (Tailscale) ou a integração Roblox."
    )


def _pacote_blender(_message: str, n: str) -> str:
    return (
        "No Blender eu trabalho em malha real: primitivas com shade smooth, "
        "materiais Principled BSDF, UVs unwrap, keyframes no action editor, "
        "e export glTF/GLB. Texturas procedurais (noise/wave) viram PNG tileable "
        "quando você pede. Peça **crie um personagem / cena / terreno / animação / "
        "textura** que eu entrego o `.py` (e o render/GLB se o Blender estiver no servidor "
        "ou no Workspace)."
    )


def _pacote_netcode(n: str) -> str:
    return (
        "Netcode de jogo: autoritativo no servidor, interpolação no cliente, "
        "predição + reconciliação para input local, snapshot delta, e — em luta/"
        "precision — rollback estilo GGPO. No Roblox: o servidor é a verdade; "
        "RemoteEvent não é estado; evite replicar cada frame. Tick 20–30 Hz com "
        "interpolação visual cobre a maioria dos cases."
    )


def _pacote_textura(n: str) -> str:
    return (
        "Textura de produção: albedo sRGB, normal em tangent space, roughness/"
        "metallic em canais lineares, AO separado, tiles 2^n (1024/2048/4096). "
        "Peça **crie uma textura** que eu gero um PNG procedural aqui no chat "
        "(sem modelo de terceiro) e o shader Blender correspondente."
    )


def _pacote_animacao(n: str) -> str:
    return (
        "Animação: keyframes com easing, ciclos que fecham (primeiro = último "
        "pose), root motion separado de gesture, e no Roblox: AnimationClip com "
        "prioridade Action/Movement. Peça **crie uma animação** para receber "
        "trilhas + script Blender com keyframe_insert."
    )


def _resposta_aberta(message: str, n: str) -> str:
    return (
        f"{IDENTIDADE}\n\n"
        f"Sobre o que você perguntou — «{message.strip()[:240]}» — eu respondo "
        "como especialista de produção, não como chatbot genérico:\n\n"
        "1. **Objetivo** — o que precisa existir no jogo/ferramenta no final.\n"
        "2. **Arquitetura** — dados, replicação, assets, e o que fica no servidor.\n"
        "3. **Execução** — passos concretos em Roblox Studio / Blender / engine.\n"
        "4. **Entrega** — se for para criar, peça com um verbo (crie, gera, monta) "
        "que eu já devolvo o arquivo neste chat.\n\n"
        "Não dependo de modelo de terceiro. Se o checkpoint ARKHER-1 estiver "
        "carregado, ele continua a resposta; se não, esta camada especialista "
        "segue no comando. Diga o recorte (plataforma, estilo, restrição) que eu "
        "afino."
    )


def responder(message: str) -> str:
    """Resposta completa para qualquer pergunta (sem provedor externo)."""
    message = (message or "").strip()
    if not message:
        return "Manda a pergunta ou o pedido de criação — eu respondo e, se for o caso, gero o arquivo aqui."
    mat = _matematica(message)
    if mat:
        return mat
    conhec = _conhecimento(message)
    # conhecimento só entra se realmente cobre o pedido
    if conhec and overlap(message, set(_WORD.findall(conhec))) >= 2:
        # se a pergunta é identidade, prioriza a identidade atual
        if re.search(r"\b(quem e voce|o que e a arkher)\b", _norm(message)):
            return IDENTIDADE
        return conhec
    return _especialista(message)
