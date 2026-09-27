"""Dezenas de fontes de modelo/textura/HDRI/anim — API pública, pasta local ou abrir no PC.

Nada de scrape de loja (CGTrader, TurboSquid, Fab, Toolbox). Mixamo/Quixel = você baixa.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

_UA = "ArkherAI/0.2 (treino educacional; https://github.com/PlexztyRBXStudiosBR/ARKHERAI_resynced)"
TIMEOUT = 10.0

# 48 sites. modo: api = busca/baixa; ingest = pasta local; abrir = HUD/navegador.
FONTES: list[dict] = [
    {"id": "polyhaven", "nome": "Poly Haven", "url": "https://polyhaven.com", "tipo": "3d+hdr+tex", "licenca": "CC0", "modo": "api"},
    {"id": "ambientcg", "nome": "AmbientCG", "url": "https://ambientcg.com", "tipo": "tex", "licenca": "CC0", "modo": "api"},
    {"id": "sketchfab", "nome": "Sketchfab", "url": "https://sketchfab.com", "tipo": "3d", "licenca": "mista", "modo": "api"},
    {"id": "archive", "nome": "Internet Archive 3D", "url": "https://archive.org", "tipo": "3d", "licenca": "por item", "modo": "api"},
    {"id": "wikimedia", "nome": "Wikimedia Commons", "url": "https://commons.wikimedia.org", "tipo": "3d+2d", "licenca": "CC", "modo": "api"},
    {"id": "openverse", "nome": "Openverse (CC Search)", "url": "https://openverse.org", "tipo": "2d+audio", "licenca": "CC", "modo": "api"},
    {"id": "godotlib", "nome": "Godot Asset Library", "url": "https://godotengine.org/asset-library", "tipo": "3d+gd", "licenca": "por asset", "modo": "api"},
    {"id": "khronos", "nome": "Khronos glTF samples", "url": "https://github.com/KhronosGroup/glTF-Sample-Models", "tipo": "3d", "licenca": "CC-BY / Apache", "modo": "api"},
    {"id": "zenodo", "nome": "Zenodo", "url": "https://zenodo.org", "tipo": "3d+dados", "licenca": "por record", "modo": "api"},
    {"id": "metmuseum", "nome": "The Met Open Access", "url": "https://www.metmuseum.org", "tipo": "2d+ref", "licenca": "CC0 (OA)", "modo": "api"},
    {"id": "cleveland", "nome": "Cleveland Museum", "url": "https://www.clevelandart.org", "tipo": "2d+ref", "licenca": "CC0", "modo": "api"},
    {"id": "nasa", "nome": "NASA Images / 3D", "url": "https://images.nasa.gov", "tipo": "2d+3d", "licenca": "NASA", "modo": "api"},
    {"id": "loc", "nome": "Library of Congress", "url": "https://www.loc.gov", "tipo": "2d+ref", "licenca": "por item", "modo": "api"},
    {"id": "smithsonian", "nome": "Smithsonian Open Access", "url": "https://www.si.edu/openaccess", "tipo": "3d+2d", "licenca": "CC0", "modo": "abrir"},
    {"id": "nih3d", "nome": "NIH 3D Print Exchange", "url": "https://3dprint.nih.gov", "tipo": "3d", "licenca": "aberta", "modo": "abrir"},
    {"id": "opengameart", "nome": "OpenGameArt", "url": "https://opengameart.org", "tipo": "3d+2d+audio", "licenca": "CC", "modo": "abrir"},
    {"id": "kenney", "nome": "Kenney.nl", "url": "https://kenney.nl/assets", "tipo": "3d+2d", "licenca": "CC0", "modo": "abrir"},
    {"id": "quaternius", "nome": "Quaternius", "url": "https://quaternius.com", "tipo": "3d", "licenca": "CC0", "modo": "abrir"},
    {"id": "kaykit", "nome": "KayKit", "url": "https://kaylousberg.itch.io", "tipo": "3d", "licenca": "CC0", "modo": "abrir"},
    {"id": "itch", "nome": "itch.io (CC0/CC-BY)", "url": "https://itch.io/game-assets/free/tag-3d", "tipo": "3d+2d", "licenca": "por pack", "modo": "abrir"},
    {"id": "blendswap", "nome": "BlendSwap", "url": "https://blendswap.com", "tipo": "3d", "licenca": "CC", "modo": "abrir"},
    {"id": "blenderkit", "nome": "BlenderKit", "url": "https://www.blenderkit.com", "tipo": "3d+tex", "licenca": "conta", "modo": "abrir"},
    {"id": "thingiverse", "nome": "Thingiverse", "url": "https://www.thingiverse.com", "tipo": "3d", "licenca": "CC + token", "modo": "abrir"},
    {"id": "printables", "nome": "Printables", "url": "https://www.printables.com", "tipo": "3d", "licenca": "por item", "modo": "abrir"},
    {"id": "myminifactory", "nome": "MyMiniFactory", "url": "https://www.myminifactory.com", "tipo": "3d", "licenca": "por item", "modo": "abrir"},
    {"id": "grabcad", "nome": "GrabCAD", "url": "https://grabcad.com", "tipo": "3d", "licenca": "conta", "modo": "abrir"},
    {"id": "claraio", "nome": "Clara.io", "url": "https://clara.io/library", "tipo": "3d", "licenca": "mista", "modo": "abrir"},
    {"id": "threejs", "nome": "three.js examples", "url": "https://threejs.org/examples", "tipo": "3d", "licenca": "MIT", "modo": "abrir"},
    {"id": "makehuman", "nome": "MakeHuman", "url": "http://www.makehumancommunity.org", "tipo": "3d", "licenca": "AGPL", "modo": "abrir"},
    {"id": "vroid", "nome": "VRoid Hub", "url": "https://hub.vroid.com", "tipo": "3d", "licenca": "conta", "modo": "abrir"},
    {"id": "mixamo", "nome": "Mixamo", "url": "https://www.mixamo.com", "tipo": "anim", "licenca": "Adobe / uso no jogo", "modo": "ingest"},
    {"id": "accurig", "nome": "AccuRIG / ActorCore", "url": "https://actorcore.reallusion.com", "tipo": "anim", "licenca": "conta", "modo": "abrir"},
    {"id": "readyplayerme", "nome": "Ready Player Me", "url": "https://readyplayer.me", "tipo": "3d", "licenca": "conta", "modo": "abrir"},
    {"id": "cmu_mocap", "nome": "CMU MoCap", "url": "http://mocap.cs.cmu.edu", "tipo": "anim", "licenca": "pesquisa", "modo": "abrir"},
    {"id": "sfu_mocap", "nome": "SFU MoCap", "url": "https://www.cs.sfu.ca/~mori/", "tipo": "anim", "licenca": "pesquisa", "modo": "abrir"},
    {"id": "sharetextures", "nome": "ShareTextures", "url": "https://www.sharetextures.com", "tipo": "tex", "licenca": "CC0", "modo": "abrir"},
    {"id": "texturecan", "nome": "TextureCan", "url": "https://www.texturecan.com", "tipo": "tex", "licenca": "CC0", "modo": "abrir"},
    {"id": "texturesme", "nome": "3DTextures.me", "url": "https://3dtextures.me", "tipo": "tex", "licenca": "CC0", "modo": "abrir"},
    {"id": "gameicons", "nome": "Game-icons.net", "url": "https://game-icons.net", "tipo": "2d", "licenca": "CC-BY", "modo": "abrir"},
    {"id": "lospec", "nome": "Lospec", "url": "https://lospec.com", "tipo": "2d", "licenca": "por paleta", "modo": "abrir"},
    {"id": "openclipart", "nome": "Openclipart", "url": "https://openclipart.org", "tipo": "2d", "licenca": "CC0", "modo": "abrir"},
    {"id": "freesound", "nome": "Freesound", "url": "https://freesound.org", "tipo": "audio", "licenca": "CC + token", "modo": "abrir"},
    {"id": "philharmonia", "nome": "Philharmonia samples", "url": "https://philharmonia.co.uk/resources/sound-samples/", "tipo": "audio", "licenca": "uso educacional", "modo": "abrir"},
    {"id": "unsplash", "nome": "Unsplash", "url": "https://unsplash.com", "tipo": "2d", "licenca": "Unsplash + token", "modo": "abrir"},
    {"id": "pexels", "nome": "Pexels", "url": "https://www.pexels.com", "tipo": "2d", "licenca": "Pexels + token", "modo": "abrir"},
    {"id": "pixabay", "nome": "Pixabay", "url": "https://pixabay.com", "tipo": "2d", "licenca": "Pixabay + token", "modo": "abrir"},
    {"id": "flickr", "nome": "Flickr Commons", "url": "https://www.flickr.com/commons", "tipo": "2d", "licenca": "Commons", "modo": "abrir"},
    {"id": "wellcome", "nome": "Wellcome Collection", "url": "https://wellcomecollection.org", "tipo": "2d", "licenca": "CC", "modo": "abrir"},
    {"id": "rijks", "nome": "Rijksmuseum", "url": "https://www.rijksmuseum.nl", "tipo": "2d", "licenca": "CC0", "modo": "abrir"},
    {"id": "europeana", "nome": "Europeana", "url": "https://www.europeana.eu", "tipo": "2d+3d", "licenca": "por item + chave", "modo": "abrir"},
    {"id": "blenderkit_open", "nome": "Blender demo files", "url": "https://www.blender.org/download/demo-files/", "tipo": "3d", "licenca": "CC-BY", "modo": "abrir"},
]


def lista() -> list[dict]:
    return list(FONTES)


def _http_json(url: str) -> dict | list:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def _falha(fid: str, e: Exception) -> dict:
    return {"ok": False, "fonte": fid, "code": "FONTE_INDISPONIVEL", "message": str(e)[:180]}


def _busca_polyhaven(q: str, n: int) -> dict:
    from backend.app.acervo import modelos
    return modelos.polyhaven_buscar(q, n)


def _busca_sketchfab(q: str, n: int) -> dict:
    from backend.app.acervo import modelos
    return modelos.sketchfab_buscar(q, limite=n)


def _busca_archive(q: str, n: int) -> dict:
    params = urllib.parse.urlencode({
        "q": f"{q} AND mediatype:(3d OR movies OR image)",
        "fl[]": ["identifier", "title", "licenseurl"],
        "rows": n,
        "output": "json",
    }, doseq=True)
    dados = _http_json(f"https://archive.org/advancedsearch.php?{params}")
    hits = []
    for doc in dados.get("response", {}).get("docs", []):
        hits.append({
            "nome": doc.get("title") or doc.get("identifier"),
            "url": f"https://archive.org/details/{doc.get('identifier', '')}",
            "licenca": doc.get("licenseurl") or "verificar",
        })
    return {"ok": True, "fonte": "archive", "resultados": hits}


def _busca_wikimedia(q: str, n: int) -> dict:
    url = (
        "https://commons.wikimedia.org/w/api.php?action=query&list=search"
        f"&srsearch={urllib.parse.quote(q + ' 3D')}"
        f"&srnamespace=6&srlimit={n}&format=json"
    )
    dados = _http_json(url)
    hits = []
    for it in dados.get("query", {}).get("search", []):
        title = it.get("title") or ""
        hits.append({"nome": title, "url": "https://commons.wikimedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_")), "licenca": "CC"})
    return {"ok": True, "fonte": "wikimedia", "resultados": hits}


def _busca_openverse(q: str, n: int) -> dict:
    url = f"https://api.openverse.org/v1/images/?q={urllib.parse.quote(q)}&page_size={n}"
    dados = _http_json(url)
    hits = []
    for it in dados.get("results", [])[:n]:
        hits.append({"nome": it.get("title"), "url": it.get("url") or it.get("foreign_landing_url"), "licenca": it.get("license")})
    return {"ok": True, "fonte": "openverse", "resultados": hits}


def _busca_godotlib(q: str, n: int) -> dict:
    url = f"https://godotengine.org/asset-library/api/asset?godot_version=4.3&max_results={n}&filter={urllib.parse.quote(q)}"
    dados = _http_json(url)
    hits = []
    for it in (dados.get("result") or [])[:n]:
        hits.append({"nome": it.get("title"), "url": it.get("browse_url") or it.get("icon_url"), "licenca": "asset-lib"})
    return {"ok": True, "fonte": "godotlib", "resultados": hits}


def _busca_zenodo(q: str, n: int) -> dict:
    url = f"https://zenodo.org/api/records?q={urllib.parse.quote(q + ' gltf OR fbx OR obj')}&size={n}&type=dataset"
    dados = _http_json(url)
    hits = []
    for it in dados.get("hits", {}).get("hits", [])[:n]:
        meta = it.get("metadata") or {}
        hits.append({"nome": meta.get("title"), "url": it.get("links", {}).get("html"), "licenca": str(meta.get("license") or "")[:80]})
    return {"ok": True, "fonte": "zenodo", "resultados": hits}


def _busca_met(q: str, n: int) -> dict:
    dados = _http_json("https://collectionapi.metmuseum.org/public/collection/v1/search?hasImages=true&q=" + urllib.parse.quote(q))
    ids = (dados.get("objectIDs") or [])[:n]
    hits = [{"nome": f"met-{i}", "url": f"https://www.metmuseum.org/art/collection/search/{i}", "licenca": "OA"} for i in ids]
    return {"ok": True, "fonte": "metmuseum", "resultados": hits}


def _busca_cleveland(q: str, n: int) -> dict:
    dados = _http_json("https://openaccess-api.clevelandart.org/api/artworks/?q=" + urllib.parse.quote(q) + f"&limit={n}")
    hits = []
    for it in dados.get("data") or []:
        hits.append({"nome": it.get("title"), "url": it.get("url"), "licenca": "CC0"})
    return {"ok": True, "fonte": "cleveland", "resultados": hits}


def _busca_nasa(q: str, n: int) -> dict:
    dados = _http_json("https://images-api.nasa.gov/search?media_type=image&q=" + urllib.parse.quote(q))
    hits = []
    for it in (dados.get("collection") or {}).get("items") or []:
        d = (it.get("data") or [{}])[0]
        hits.append({"nome": d.get("title"), "url": f"https://images.nasa.gov/details-{d.get('nasa_id')}", "licenca": "NASA"})
        if len(hits) >= n:
            break
    return {"ok": True, "fonte": "nasa", "resultados": hits}


def _busca_loc(q: str, n: int) -> dict:
    dados = _http_json("https://www.loc.gov/search/?fo=json&q=" + urllib.parse.quote(q + " 3d"))
    hits = []
    for it in (dados.get("results") or [])[:n]:
        hits.append({"nome": it.get("title"), "url": it.get("id") or it.get("url"), "licenca": "LoC"})
    return {"ok": True, "fonte": "loc", "resultados": hits}


def _busca_ambientcg(q: str, n: int) -> dict:
    dados = _http_json(f"https://ambientcg.com/api/v2/full_json?limit={n}&q={urllib.parse.quote(q)}")
    hits = []
    found = dados.get("foundAssets") or dados.get("assets") or []
    if isinstance(dados, dict) and not found:
        found = list(dados.values())[:n] if dados else []
    if isinstance(found, list):
        for it in found[:n]:
            if isinstance(it, dict):
                hits.append({"nome": it.get("assetId") or it.get("name"), "url": "https://ambientcg.com/a/" + str(it.get("assetId") or ""), "licenca": "CC0"})
    return {"ok": True, "fonte": "ambientcg", "resultados": hits}


def _busca_khronos(q: str, n: int) -> dict:
    nomes = ["Box", "Duck", "Avocado", "DamagedHelmet", "BoomBox", "Fox", "Lantern", "WaterBottle"]
    ql = q.lower()
    pick = [x for x in nomes if ql in x.lower()] or nomes[:n]
    hits = [{"nome": x, "url": f"https://github.com/KhronosGroup/glTF-Sample-Models/tree/main/2.0/{x}", "licenca": "CC-BY"} for x in pick[:n]]
    return {"ok": True, "fonte": "khronos", "resultados": hits}


_BUSCA = {
    "polyhaven": _busca_polyhaven,
    "sketchfab": _busca_sketchfab,
    "archive": _busca_archive,
    "wikimedia": _busca_wikimedia,
    "openverse": _busca_openverse,
    "godotlib": _busca_godotlib,
    "zenodo": _busca_zenodo,
    "metmuseum": _busca_met,
    "cleveland": _busca_cleveland,
    "nasa": _busca_nasa,
    "loc": _busca_loc,
    "ambientcg": _busca_ambientcg,
    "khronos": _busca_khronos,
}


def colher_todas(consulta: str, limite_por: int = 2) -> dict:
    """Varre o catálogo. API = busca; o resto devolve URL pra abrir/ingerir."""
    consulta = (consulta or "game asset").strip()[:80]
    por_fonte = []
    n_api = 0
    n_hits = 0
    for f in FONTES:
        fid = f["id"]
        if fid in _BUSCA:
            try:
                r = _BUSCA[fid](consulta, max(1, min(4, limite_por)))
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
                r = _falha(fid, e)
            n_api += 1
            n_hits += len(r.get("resultados") or []) if isinstance(r, dict) else 0
        else:
            r = {
                "ok": True,
                "fonte": fid,
                "modo": f["modo"],
                "url": f["url"],
                "message": "abra no PC (HUD) ou jogue arquivos em ArkherAITraining/" + fid,
            }
        por_fonte.append({"id": fid, "nome": f["nome"], "tipo": f["tipo"], "licenca": f["licenca"], "modo": f["modo"], "url": f["url"], "busca": r})
    return {
        "ok": True,
        "consulta": consulta,
        "n_sites": len(FONTES),
        "n_api": n_api,
        "n_hits": n_hits,
        "fontes": por_fonte,
    }
