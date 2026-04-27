"""
scenes/mosaic.py
Cena 'mosaic': múltiplas imagens surgindo lado a lado com slide de baixo para cima.

Ideal para: "usei React, Postgres, Express, Node" → 4 ícones 9:16 compondo 16:9.

JSON de exemplo:
{
  "id": 2,
  "type": "mosaic",
  "duration": 9.0,
  "images": ["images/react.png", "images/postgres.png", "images/node.png"],
  "appear_interval": 1.8,
  "slide_duration": 0.42,
  "effect": "ken_burns_random",
  "overlay": ["grain"],
  "bg_color": [12, 12, 12],
  "transition_out": "crossfade"
}
"""
import numpy as np
from effects.ken_burns import kb_frame, resolve_kb
from effects.overlays import apply_fx
from utils.image import load_image


def scene_mosaic(scene: dict, W: int, H: int, fps: int):
    """
    Constrói um VideoClip de mosaico com aparição sequencial das imagens.
    """
    from moviepy import VideoClip

    dur = float(scene["duration"])
    paths = scene["images"]
    n = len(paths)
    interval = float(scene.get("appear_interval", dur / (n + 1.5)))
    slide_t = float(scene.get("slide_duration", 0.42))
    overlays = scene.get("overlay", ["grain"])
    bg = tuple(scene.get("bg_color", [12, 12, 12]))
    scene_id = scene.get("id", 0)

    slot_w = W // n
    slot_h = H

    # Pré-carrega imagens e presets Ken Burns (determinístico por seed)
    slots = []
    for i, path in enumerate(paths):
        img = load_image(path, slot_w, slot_h)
        z0, z1, px, py = resolve_kb("ken_burns_random", seed=scene_id * 1000 + i)
        slots.append((img, z0, z1, px, py))

    def make_frame(t: float) -> np.ndarray:
        canvas = np.full((H, W, 3), bg, dtype=np.uint8)

        for i, (img, z0, z1, px, py) in enumerate(slots):
            t_appear = i * interval
            if t < t_appear:
                continue

            lt = t - t_appear
            raw = min(lt / slide_t, 1.0)
            # ease-out cúbico: arranca rápido, desacelera suavemente
            p = 1.0 - (1.0 - raw) ** 3

            frame = kb_frame(img, lt, dur, z0, z1, px, py, slot_w, slot_h)

            x0 = i * slot_w
            y_top = int((1.0 - p) * H)  # desliza de H → 0
            vis = H - y_top
            if vis > 0:
                canvas[y_top:H, x0 : x0 + slot_w] = frame[:vis]

        return apply_fx(canvas, t, fps, W, H, overlays)

    return VideoClip(make_frame, duration=dur).with_fps(fps)
