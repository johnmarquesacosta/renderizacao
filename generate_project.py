#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║  generate_project.py  —  Gerador de project.json            ║
║                                                              ║
║  Escaneia a pasta de imagens e cria o arquivo de projeto     ║
║  com cenas mistas (single + mosaic) de forma aleatória.      ║
║                                                              ║
║  Uso:                                                        ║
║    python generate_project.py                                ║
║    python generate_project.py images/ audio.wav              ║
║    python generate_project.py images/ audio.wav project.json ║
╚══════════════════════════════════════════════════════════════╝
"""

import json
import sys
import os
import glob
import random
from pathlib import Path


# ── Configurações de geração ──────────────────────────────────

SINGLE_DUR_RANGE  = (3.5, 7.0)    # (min, max) segundos por cena single
MOSAIC_DUR_RANGE  = (6.0, 11.0)   # (min, max) segundos por cena mosaic
MOSAIC_PROB       = 0.35           # probabilidade de uma cena ser mosaic
MOSAIC_N_RANGE    = (2, 4)        # número de imagens numa cena mosaic

# Efeitos disponíveis para cenas single
SINGLE_EFFECTS = [
    "ken_burns_in",
    "ken_burns_out",
    "ken_burns_pan_left",
    "ken_burns_pan_right",
    "ken_burns_drift_in",
    "ken_burns_drift_out",
    "ken_burns_random",
]

# Combinações de overlays para variação estética
OVERLAY_OPTIONS = [
    ["grain", "vignette"],
    ["grain", "vignette"],          # duplicado = mais frequente
    ["grain", "vignette"],
    ["grain"],
    ["grain", "vignette", "desaturate"],
]


# ══════════════════════════════════════════════════════════════
#  GERAÇÃO DE CENAS
# ══════════════════════════════════════════════════════════════

def make_single(scene_id: int, image: str) -> dict:
    dur = round(random.uniform(*SINGLE_DUR_RANGE), 1)
    return {
        "id":             scene_id,
        "type":           "single",
        "duration":       dur,
        "images":         [image],
        "effect":         random.choice(SINGLE_EFFECTS),
        "overlay":        random.choice(OVERLAY_OPTIONS),
        "transition_out": "crossfade",
    }


def make_mosaic(scene_id: int, images: list) -> dict:
    n   = len(images)
    dur = round(random.uniform(*MOSAIC_DUR_RANGE), 1)
    # Intervalo entre surgimento de cada imagem
    interval = round(dur / (n + 2.2), 2)
    return {
        "id":               scene_id,
        "type":             "mosaic",
        "duration":         dur,
        "images":           images,
        "appear_interval":  interval,
        "slide_duration":   0.42,
        "effect":           random.choice(["ken_burns_in", "ken_burns_random"]),
        "overlay":          ["grain"],
        "bg_color":         [12, 12, 12],
        "transition_out":   "crossfade",
    }


def generate_scenes(images: list) -> list:
    """
    Distribui as imagens em cenas single e mosaic de forma aleatória.
    """
    scenes = []
    i      = 0
    sid    = 1

    while i < len(images):
        remaining = len(images) - i
        min_mosaic = MOSAIC_N_RANGE[0]

        if remaining >= min_mosaic and random.random() < MOSAIC_PROB:
            # Cena mosaic
            n = min(
                random.randint(*MOSAIC_N_RANGE),
                remaining
            )
            scenes.append(make_mosaic(sid, images[i:i + n]))
            i   += n
        else:
            # Cena single
            scenes.append(make_single(sid, images[i]))
            i += 1

        sid += 1

    return scenes


# ══════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════

def main():
    images_dir  = sys.argv[1] if len(sys.argv) > 1 else "images"
    audio_file  = sys.argv[2] if len(sys.argv) > 2 else "audio.wav"
    output_json = sys.argv[3] if len(sys.argv) > 3 else "project.json"

    # Coleta imagens na ordem natural
    exts   = ["*.png", "*.jpg", "*.jpeg", "*.webp"]
    images = []
    for ext in exts:
        images.extend(sorted(glob.glob(os.path.join(images_dir, ext))))

    if not images:
        print(f"❌  Nenhuma imagem encontrada em: {images_dir!r}")
        print("    Certifique-se de que a pasta existe e contém .png/.jpg")
        sys.exit(1)

    print(f"📁  {len(images)} imagens encontradas em '{images_dir}'")

    scenes    = generate_scenes(images)
    total_dur = sum(s["duration"] for s in scenes)

    # Conta tipos
    n_single = sum(1 for s in scenes if s["type"] == "single")
    n_mosaic = sum(1 for s in scenes if s["type"] == "mosaic")

    project = {
        "title":       Path(os.getcwd()).name,
        "audio":       audio_file,
        "fps":         30,
        "resolution":  [1920, 1080],
        "output":      "output.mp4",
        "transitions": {
            "default":  "crossfade",
            "duration": 0.5
        },
        "scenes":      scenes,
    }

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(project, f, indent=2, ensure_ascii=False)

    print(f"\n✅  {output_json} gerado com sucesso!")
    print(f"    {len(scenes)} cenas total")
    print(f"    ├─ {n_single} cenas single")
    print(f"    └─ {n_mosaic} cenas mosaic "
          f"({sum(len(s['images']) for s in scenes if s['type']=='mosaic')} imagens)")
    print(f"    Duração estimada: ~{total_dur/60:.1f} minutos\n")
    print(f"▶  Renderizar:  python render.py {output_json}")
    print(f"   (Dica: edite o JSON antes de renderizar para ajustar cenas)\n")


if __name__ == "__main__":
    main()
