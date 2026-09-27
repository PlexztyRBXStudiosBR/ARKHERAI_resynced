"""Godot 4 — motor principal da ARKHER. Artefatos reais (.tscn, .gd, project.godot).

Roblox continua no Vault e nas abas Places/Luau; aqui o jogo nasce no Godot.
Sem template-AI: cena com chão irregular, luz, player e HUD de canto.
"""
from __future__ import annotations

def _limpo(s: str) -> str:
    return (s or "").replace('"', "").replace("\n", " ")[:80]


def _pack(nome: str, corpo: str, descricao: str, como: str) -> dict:
    return {
        "descricao": descricao,
        "arquivo": {"nome": nome, "conteudo": corpo},
        "como_usar": como,
        "motor": "godot4",
    }


def gerar(recipe: str, seed: int, prompt: str = "") -> dict:
    tema = (prompt or "acao cooperativo").strip()[:80]
    s = int(seed) & 0x7FFFFFFF
    nome = f"ARKHER_{tema.replace(' ', '_')[:24]}_{s}"
    if recipe == "projeto":
        corpo = (
            "config_version=5\n\n"
            "[application]\n"
            f'config/name="{_limpo(nome)}"\n'
            'run/main_scene="res://scenes/main.tscn"\n'
            "config/features=PackedStringArray(\"4.3\", \"Forward Plus\")\n\n"
            "[rendering]\n"
            'renderer/rendering_method="forward_plus"\n'
            "lights_and_shadows/directional_shadow/size=4096\n\n"
            "[physics]\n"
            "3d/physics_engine=\"GodotPhysics3D\"\n"
        )
        return _pack(
            f"project_{s}.godot",
            corpo,
            f"Projeto Godot 4 '{nome}'. Cole como project.godot na pasta do jogo.",
            "Godot 4: Import → pasta do projeto. Depois abra scenes/main.tscn.",
        )
    if recipe == "cena3d":
        x = 8 + (s % 7)
        z = -6 - (s % 5)
        corpo = f"""[gd_scene load_steps=3 format=3]

[sub_resource type="BoxMesh" id="chao_mesh"]
size = Vector3(48, 1, 48)

[sub_resource type="BoxMesh" id="marco_mesh"]
size = Vector3(4, 14, 4)

[node name="Main" type="Node3D"]

[node name="Chao" type="StaticBody3D" parent="."]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, -0.5, 0)

[node name="Mesh" type="MeshInstance3D" parent="Chao"]
mesh = SubResource("chao_mesh")

[node name="Col" type="CollisionShape3D" parent="Chao"]

[node name="Marco" type="StaticBody3D" parent="."]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, {x}, 7, {z})

[node name="Mesh" type="MeshInstance3D" parent="Marco"]
mesh = SubResource("marco_mesh")

[node name="Sol" type="DirectionalLight3D" parent="."]
transform = Transform3D(0.8, -0.4, 0.4, 0, 0.7, 0.7, -0.6, -0.56, 0.56, 8, 18, 4)
light_energy = 1.15
shadow_enabled = true

[node name="Camera3D" type="Camera3D" parent="."]
transform = Transform3D(1, 0, 0, 0, 0.92, 0.39, 0, -0.39, 0.92, 0, 8, 16)
current = true

[node name="Spawn" type="Marker3D" parent="."]
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 1.2, 8)
"""
        return _pack(f"main_{s}.tscn", corpo, f"Cena 3D Godot do tema '{tema}' (chão + marco + luz).", "Arraste para res://scenes/main.tscn e rode F5.")
    if recipe == "player":
        corpo = f"""extends CharacterBody3D
# ARKHER Godot player seed {s} — {tema}
const SPEED := 7.2
const JUMP := 6.4
var gravity: float = ProjectSettings.get_setting("physics/3d/default_gravity")

func _physics_process(delta: float) -> void:
	if not is_on_floor():
		velocity.y -= gravity * delta
	if Input.is_action_just_pressed("ui_accept") and is_on_floor():
		velocity.y = JUMP
	var d := Input.get_vector("ui_left", "ui_right", "ui_up", "ui_down")
	var dir := (transform.basis * Vector3(d.x, 0, d.y)).normalized()
	if dir:
		velocity.x = dir.x * SPEED
		velocity.z = dir.z * SPEED
	else:
		velocity.x = move_toward(velocity.x, 0, SPEED)
		velocity.z = move_toward(velocity.z, 0, SPEED)
	move_and_slide()
"""
        return _pack(f"player_{s}.gd", corpo, "CharacterBody3D com gravidade, pulo e eixos — GDScript 4.", "Anexe ao nó Player da cena. Input Map: ui_left/right/up/down/accept.")
    if recipe == "hud":
        corpo = f"""[gd_scene format=3]

[node name="Hud" type="CanvasLayer"]

[node name="Placa" type="Panel" parent="."]
offset_left = 16.0
offset_top = -88.0
offset_right = 296.0
offset_bottom = -16.0
anchor_top = 1.0
anchor_bottom = 1.0

[node name="Nome" type="Label" parent="Placa"]
offset_left = 12.0
offset_top = 10.0
offset_right = 260.0
offset_bottom = 34.0
text = "{_limpo(nome)}"

[node name="Estado" type="Label" parent="Placa"]
offset_left = 12.0
offset_top = 36.0
offset_right = 260.0
offset_bottom = 60.0
text = "ARKHER · Godot · seed {s}"
"""
        return _pack(f"hud_{s}.tscn", corpo, "HUD de canto (não pílula, não centro). Godot Control.", "Instance na Main. Sem fonte Inter/Roboto.")
    if recipe == "plataforma":
        corpo = f"""extends Node2D
# plataforma 2D seed {s}
func _ready() -> void:
	var chao := ColorRect.new()
	chao.color = Color(0.23, 0.2, 0.16)
	chao.size = Vector2(640, 24)
	chao.position = Vector2(0, 340)
	add_child(chao)
	var bloco := ColorRect.new()
	bloco.color = Color(0.42, 0.33, 0.22)
	bloco.size = Vector2(96, 18)
	bloco.position = Vector2({80 + s % 40}, 220)
	add_child(bloco)
"""
        return _pack(f"plataforma_{s}.gd", corpo, "Esboço 2D de plataforma (ColorRect) — depois troca por TileMap.", "Cena 2D vazia + este script. Roblox não entra aqui.")
    # export
    corpo = (
        "[preset.0]\n"
        'name="Windows Desktop"\n'
        "platform=\"Windows Desktop\"\n"
        "runnable=true\n"
        "export_filter=\"all_resources\"\n"
        f"seed_arkher={s}\n"
    )
    return _pack(f"export_{s}.cfg", corpo, "Preset de export Windows. Confirme no Godot antes de publicar.", "Godot: Project → Export → Importar este preset.")
