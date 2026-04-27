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
import random
import numpy as np
from PIL import Image, ImageDraw

from effects.ken_burns import kb_frame, resolve_kb
from effects.overlays import apply_fx
from utils.image import get_layer_images, load_image


def _to_bw(frame: np.ndarray) -> np.ndarray:
    """Converte frame RGB para preto e branco (luminancia ponderada)."""
    lum = (
        frame[:, :, 0] * 0.299
        + frame[:, :, 1] * 0.587
        + frame[:, :, 2] * 0.114
    ).astype(np.uint8)
    return np.stack([lum, lum, lum], axis=2)


def _draw_grid(
    canvas_pil: Image.Image,
    t: float,
    spacing: int,
    color_rgb: tuple,
    alpha: float,
    dx: int,
    dy: int,
    speed: float,
) -> Image.Image:
    """Desenha grid animado sobre canvas PIL."""
    W, H = canvas_pil.size
    draw = ImageDraw.Draw(canvas_pil, "RGBA")
    ox = int(t * speed * dx) % spacing
    oy = int(t * speed * dy) % spacing
    line_color = (*color_rgb, int(alpha * 255))

    x = ox - spacing
    while x < W + spacing:
        draw.line([(x, 0), (x, H)], fill=line_color, width=1)
        x += spacing

    y = oy - spacing
    while y < H + spacing:
        draw.line([(0, y), (W, y)], fill=line_color, width=1)
        y += spacing

    return canvas_pil


def scene_mosaic(scene: dict, W: int, H: int, fps: int):
    """
    Constrói um VideoClip de mosaico com grid animado e slots P&B.
    """
    from moviepy import VideoClip

    dur = float(scene["duration"])
    layers = get_layer_images(scene)
    paths = [layer["image"] for layer in layers]
    n = len(paths)
    interval = float(scene.get("appear_interval", dur / (n + 1.5)))
    slide_t = float(scene.get("slide_duration", 0.42))
    overlays = scene.get("overlay", ["grain"])

    outer = int(scene.get("outer_margin", 60))
    gap = int(scene.get("inner_gap", 24))
    bg = tuple(scene.get("bg_color", [13, 13, 26]))
    grid_color = tuple(scene.get("grid_color", [200, 210, 230]))
    grid_alpha = float(scene.get("grid_alpha", 0.15))
    grid_spacing = int(scene.get("grid_spacing", 90))
    grid_speed = float(scene.get("grid_speed", 12.0))
    scene_id = scene.get("id", 0)

    avail_w = W - 2 * outer - (n - 1) * gap
    avail_h = H - 2 * outer
    slot_w = max(1, avail_w // max(n, 1))
    slot_h = max(1, avail_h)
    x_positions = [outer + i * (slot_w + gap) for i in range(n)]
    y_start = outer

    # Grid animation direction (random per execution)
    rng = random.Random()
    grid_dx = rng.choice([-1, 0, 1])
    grid_dy = rng.choice([-1, 0, 1])
    if grid_dx == 0 and grid_dy == 0:
        grid_dx = rng.choice([-1, 1])

    # Pre-load images and Ken Burns presets
    slots = []
    for i, path in enumerate(paths):
        img = load_image(path, slot_w, slot_h)
        z0, z1, px, py = resolve_kb("ken_burns_random", seed=scene_id * 1000 + i)
        slots.append((img, z0, z1, px, py))

    def make_frame(t: float) -> np.ndarray:
        base = np.full((H, W, 3), bg, dtype=np.uint8)
        pil = Image.fromarray(base)
        pil = _draw_grid(
            pil, t, grid_spacing, grid_color, grid_alpha, grid_dx, grid_dy, grid_speed
        )
        canvas = np.array(pil)

        for i, (img, z0, z1, px, py) in enumerate(slots):
            t_appear = i * interval
            if t < t_appear:
                continue

            lt = t - t_appear
            raw = min(lt / slide_t, 1.0)
            p = 1.0 - (1.0 - raw) ** 3

            frame = kb_frame(img, lt, dur, z0, z1, px, py, slot_w, slot_h)
            frame = _to_bw(frame)

            x0 = x_positions[i]
            y_top = int(y_start + (1.0 - p) * slot_h)
            vis = y_start + slot_h - y_top
            if vis > 0:
                canvas[y_top : y_top + vis, x0 : x0 + slot_w] = frame[:vis]

        return apply_fx(canvas, t, fps, W, H, overlays)

    return VideoClip(make_frame, duration=dur).with_fps(fps)
