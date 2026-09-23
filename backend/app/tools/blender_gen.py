"""Conector Blender do ARKHER — geração 3D REAL por scripts do próprio projeto.

Dois modos honestos:
1. Blender instalado no servidor (binário `blender` ou env ARKHER_BLENDER):
   a ARKHER executa o script em modo headless e devolve os artefatos reais
   (.glb + render .png) empacotados em zip.
2. Sem Blender no servidor: devolve o script .py pronto para o usuário rodar
   no Blender dele (a execução real acontece na máquina do usuário).

Nenhuma máquina é controlada remotamente; o Blender roda onde o dono decidir.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

GEN_TIMEOUT_S = 240


# ------------------------------------------------------------------ scripts
_BASE_HEADER = '''"""Cena gerada pela ARKHER AI — rode no Blender 3.6+ (File > Open... ou
blender --background --python este_arquivo.py). Saída em ./arkher_saida/
"""
import bpy, math, random, os

SEED = {seed}
rng = random.Random(SEED)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "arkher_saida")
os.makedirs(OUT, exist_ok=True)

# cena limpa
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
for c in list(bpy.data.collections):
    if c.name != "Collection":
        bpy.data.collections.remove(c)

scene = bpy.context.scene
scene.render.engine = "BLENDER_EEVEE"
scene.render.resolution_x = 640
scene.render.resolution_y = 360
scene.render.image_settings.file_format = "PNG"
'''

_TERRENO = '''
# ---- terreno heightmap determinístico ----
bpy.ops.mesh.primitive_grid_add(x_subdivisions=28, y_subdivisions=28, size=20)
terreno = bpy.context.object
terreno.name = "Terreno"
fases = [(rng.uniform(0, 6.28), rng.uniform(0.35, 1.4), rng.uniform(0.6, 1.6)) for _ in range(4)]
for v in terreno.data.vertices:
    h = 0.0
    for fase, freq, peso in fases:
        h += math.sin(v.co.x * freq + fase) * math.cos(v.co.y * freq * 0.9 + fase * 0.7) * peso
    v.co.z = h * 1.4
bpy.ops.object.shade_smooth()

mat = bpy.data.materials.new("Terra")
mat.use_nodes = True
bsdf = mat.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.22, 0.42, 0.18, 1.0)
bsdf.inputs["Roughness"].default_value = 0.9
terreno.data.materials.append(mat)
'''

_CENA = '''
# ---- cena de primitivas com materiais ----
posicoes = [(x * 2.6 - 3.9, 0, 0.6) for x in range(4)]
cores = [(0.85, 0.23, 0.2, 1), (0.2, 0.5, 0.9, 1), (0.9, 0.75, 0.15, 1), (0.3, 0.8, 0.55, 1)]
criadores = [
    lambda p: bpy.ops.mesh.primitive_cube_add(size=1.2, location=p),
    lambda p: bpy.ops.mesh.primitive_uv_sphere_add(radius=0.75, location=p),
    lambda p: bpy.ops.mesh.primitive_cone_add(radius1=0.8, depth=1.4, location=p),
    lambda p: bpy.ops.mesh.primitive_torus_add(major_radius=0.7, minor_radius=0.25, location=p),
]
for i, (p, cor) in enumerate(zip(posicoes, cores)):
    z = p[2] + rng.uniform(-0.1, 0.3)
    criadores[i]((p[0], p[1], z))
    obj = bpy.context.object
    obj.name = f"Prop_{i}"
    obj.rotation_euler.z = rng.uniform(0, 6.28)
    m = bpy.data.materials.new(f"Mat_{i}")
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = cor
    obj.data.materials.append(m)

bpy.ops.mesh.primitive_plane_add(size=24, location=(0, 0, -0.05))
chao = bpy.context.object
chao.name = "Chao"
mc = bpy.data.materials.new("Chao")
mc.use_nodes = True
mc.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.12, 0.13, 0.16, 1)
mc.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.95
chao.data.materials.append(mc)
'''

_PERSONAGEM = '''
# ---- personagem robô primitivo (base para prototipagem) ----
def parte(criador, nome, cor, escala=(1, 1, 1)):
    criador()
    o = bpy.context.object
    o.name = nome
    o.scale = escala
    m = bpy.data.materials.new(nome + "_mat")
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = cor
    o.data.materials.append(m)
    return o

parte(lambda: bpy.ops.mesh.primitive_capsule_add(radius=0.45, depth=0.9, location=(0, 0, 1.35)),
      "Corpo", (0.25, 0.45, 0.85, 1))
parte(lambda: bpy.ops.mesh.primitive_uv_sphere_add(radius=0.42, location=(0, 0, 2.35)),
      "Cabeca", (0.85, 0.85, 0.88, 1))
parte(lambda: bpy.ops.mesh.primitive_uv_sphere_add(radius=0.07, location=(0.16, 0.36, 2.42)),
      "Olho_D", (0.05, 0.9, 0.9, 1))
parte(lambda: bpy.ops.mesh.primitive_uv_sphere_add(radius=0.07, location=(-0.16, 0.36, 2.42)),
      "Olho_E", (0.05, 0.9, 0.9, 1))
parte(lambda: bpy.ops.mesh.primitive_cylinder_add(radius=0.13, depth=1.0, location=(0.62, 0, 1.45)),
      "Braco_D", (0.3, 0.32, 0.4, 1))
parte(lambda: bpy.ops.mesh.primitive_cylinder_add(radius=0.13, depth=1.0, location=(-0.62, 0, 1.45)),
      "Braco_E", (0.3, 0.32, 0.4, 1))
parte(lambda: bpy.ops.mesh.primitive_cylinder_add(radius=0.16, depth=0.95, location=(0.25, 0, 0.48)),
      "Perna_D", (0.2, 0.22, 0.3, 1))
parte(lambda: bpy.ops.mesh.primitive_cylinder_add(radius=0.16, depth=0.95, location=(-0.25, 0, 0.48)),
      "Perna_E", (0.2, 0.22, 0.3, 1))

bpy.ops.mesh.primitive_plane_add(size=16, location=(0, 0, 0))
chao = bpy.context.object
chao.name = "Chao"
'''

_LUZ_CAMERA = '''
# ---- iluminação e câmera ----
bpy.ops.object.light_add(type="SUN", location=(6, -4, 9))
sol = bpy.context.object
sol.data.energy = 3.2
sol.rotation_euler = (math.radians(48), math.radians(12), math.radians(30))

bpy.ops.object.light_add(type="AREA", location=(-5, -6, 5))
preench = bpy.context.object
preench.data.energy = 120
preench.data.size = 4

bpy.ops.object.camera_add(location=(8.5, -8.5, 5.2))
cam = bpy.context.object
direction = (0, 0, 1.0)
cam.rotation_mode = "XYZ"
cam.rotation_euler = (math.radians(68), 0, math.radians(45))
scene.camera = cam

scene.world.use_nodes = True
bg = scene.world.node_tree.nodes["Background"]
bg.inputs["Color"].default_value = (0.06, 0.08, 0.12, 1)

# ---- saída real: GLB + render ----
scene.render.filepath = os.path.join(OUT, f"{NOME}_seed{SEED}.png")
bpy.ops.render.render(write_still=True)
bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, f"{NOME}_seed{SEED}.glb"))
print("ARKHER_OK:", os.path.join(OUT, f"{NOME}_seed{SEED}.glb"))
'''

CENAS = {
    "terreno": (_TERRENO, "Terreno"),
    "cena": (_CENA, "Cena"),
    "personagem": (_PERSONAGEM, "Personagem"),
}


def gerar_script(cena: str, seed: int) -> str:
    cena = (cena or "").strip().lower()
    if cena not in CENAS:
        raise ValueError(f"Cena desconhecida. Opções: {', '.join(sorted(CENAS))}")
    corpo, nome = CENAS[cena]
    script = _BASE_HEADER.format(seed=int(seed)) + corpo + _LUZ_CAMERA
    return f'NOME = "{nome}"\n' + script


# ------------------------------------------------------------------ execução
def blender_bin() -> str | None:
    env = os.environ.get("ARKHER_BLENDER", "")
    if env and Path(env).is_file():
        return env
    return shutil.which("blender")


def executar(script: str, nome_base: str) -> dict | None:
    """Roda o script no Blender headless se disponível. Retorna artefatos ou None."""
    binario = blender_bin()
    if binario is None:
        return None
    tmp = Path(tempfile.mkdtemp(prefix="arkher_blender_"))
    script_path = tmp / "cena_arkher.py"
    script_path.write_text(script, encoding="utf-8")
    try:
        proc = subprocess.run(
            [binario, "--background", "--python", str(script_path)],
            capture_output=True, text=True, timeout=GEN_TIMEOUT_S, cwd=str(tmp),
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr[-800:] or "Blender terminou com erro")
        saida = tmp / "arkher_saida"
        artefatos = sorted(saida.glob("*")) if saida.is_dir() else []
        if not artefatos:
            raise RuntimeError("Blender rodou mas não gerou artefatos")
        zip_path = tmp / f"{nome_base}_arkher.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for f in artefatos:
                z.write(f, f.name)
        import base64

        return {
            "nome": zip_path.name,
            "conteudo_b64": base64.b64encode(zip_path.read_bytes()).decode("ascii"),
            "itens": [f.name for f in artefatos],
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
