# ARKHER Ponte Blender v1 — construção/modelagem ao vivo na cena aberta
#
# Instalação (pedida pela ARKHER quando você autoriza a ponte):
#   1. Salve este arquivo como arkher_ponte_blender.py
#   2. Blender → Edit → Preferences → Add-ons → Install… → selecione o arquivo
#   3. Ative "ARKHER Ponte" e abra o painel N → aba "ARKHER" na viewport 3D
#
# Uso: peça a construção no chat da ARKHER, configure servidor + token no
# painel e clique em "Construir agora". Ela cria as peças como MESHES REAIS
# (com material e cor) dentro da sua cena — modelagem de verdade.
#
# Você controla o Blender. A ARKHER só modela. Este addon fala apenas com o
# servidor ARKHER que VOCÊ configurar.

bl_info = {
    "name": "ARKHER Ponte",
    "author": "ARKHER AI",
    "version": (1, 0, 0),
    "blender": (3, 6, 0),
    "location": "3D Viewport > Painel N > ARKHER",
    "description": "Recebe construções da ARKHER e modela peça por peça na cena aberta.",
    "category": "3D View",
}

import bpy
import json
import urllib.request


def _cubo(nome, pos, size, cor_rgb, cache_mats):
    """Cria uma peça real (mesh + material) sem depender de contexto."""
    key = tuple(int(c) for c in cor_rgb)
    mat = cache_mats.get(key)
    if mat is None:
        mat = bpy.data.materials.new("ARKHER_Mat_%d%d%d" % key)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        if bsdf is not None:
            bsdf.inputs["Base Color"].default_value = (
                key[0] / 255.0, key[1] / 255.0, key[2] / 255.0, 1.0,
            )
        cache_mats[key] = mat

    sx, sy, sz = size
    x, y, z = pos
    verts = [
        (x - sx / 2, y - sy / 2, z - sz / 2), (x + sx / 2, y - sy / 2, z - sz / 2),
        (x + sx / 2, y + sy / 2, z - sz / 2), (x - sx / 2, y + sy / 2, z - sz / 2),
        (x - sx / 2, y - sy / 2, z + sz / 2), (x + sx / 2, y - sy / 2, z + sz / 2),
        (x + sx / 2, y + sy / 2, z + sz / 2), (x - sx / 2, y + sy / 2, z + sz / 2),
    ]
    faces = [
        (0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1),
        (2, 6, 7, 3), (0, 3, 7, 4), (1, 5, 6, 2),
    ]
    mesh = bpy.data.meshes.new("ARKHER_" + nome)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(nome, mesh)
    obj.data.materials.append(mat)
    return obj


class ARKHER_OT_Construir(bpy.types.Operator):
    bl_idname = "arkher.construir"
    bl_label = "Construir agora"
    bl_description = "Busca a construção pendente na ARKHER e modela na cena"

    def execute(self, context):
        prefs = context.preferences.addons[__name__].preferences
        url = (prefs.url or "").rstrip("/") or "http://127.0.0.1:8710"
        if not prefs.token:
            self.report({"WARNING"}, "Configure o token ARKHER no painel N > ARKHER.")
            return {"CANCELLED"}
        try:
            req = urllib.request.Request(
                url + "/api/build/proximo",
                headers={"X-Arkher-Token": prefs.token},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                dados = json.loads(resp.read().decode("utf-8"))
        except Exception:
            self.report({"ERROR"}, "Falha ao falar com o servidor ARKHER.")
            return {"CANCELLED"}
        ops_lista = dados.get("ops") or []
        if not ops_lista:
            self.report({"INFO"}, "Nenhuma construção pendente. Peça uma no chat primeiro.")
            return {"CANCELLED"}

        col = bpy.data.collections.new("ARKHER_Build")
        context.scene.collection.children.link(col)
        cache_mats = {}
        total = 0
        for op in ops_lista:
            if op.get("op") != "part":
                continue
            obj = _cubo(
                op.get("nome", "Part"),
                (op["pos"][0], op["pos"][1], op["pos"][2]),
                op["size"],
                op.get("cor", (160, 160, 160)),
                cache_mats,
            )
            col.objects.link(obj)
            total += 1
        self.report({"INFO"}, "ARKHER construiu %d peças na coleção ARKHER_Build." % total)
        return {"FINISHED"}


class ARKHER_PT_Painel(bpy.types.Panel):
    bl_label = "ARKHER Ponte"
    bl_idname = "ARKHER_PT_painel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ARKHER"

    def draw(self, context):
        prefs = context.preferences.addons["arkher_ponte_blender"].preferences
        layout = self.layout
        layout.prop(prefs, "url")
        layout.prop(prefs, "token")
        layout.operator("arkher.construir", icon="MESH_CUBE")


class ARKHER_Prefs(bpy.types.AddonPreferences):
    bl_idname = "arkher_ponte_blender"
    url: bpy.props.StringProperty(name="Servidor ARKHER", default="http://127.0.0.1:8710")
    token: bpy.props.StringProperty(name="Token", subtype="PASSWORD")

    def draw(self, context):
        self.layout.prop(self, "url")
        self.layout.prop(self, "token")


classes = (ARKHER_OT_Construir, ARKHER_PT_Painel, ARKHER_Prefs)


def register():
    for c in classes:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)


if __name__ == "__main__":
    register()
