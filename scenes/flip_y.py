"""
scenes/flip_y.py
Cena 'flip_y': rotacao 3D no eixo Y alternando entre duas imagens.
"""
import math
import numpy as np
from PIL import Image

from effects.overlays import apply_fx
from utils.image import _resize, get_layer_images, load_image


def scene_flip_y(scene: dict, W: int, H: int, fps: int):
    """Constroi um VideoClip com flip 3D no eixo Y."""
    from moviepy import VideoClip

    dur = float(scene["duration"])
    half = dur / 2.0
    overlays = scene.get("overlay", ["grain", "vignette"])

    layers = get_layer_images(scene)
    if not layers:
        raise ValueError("flip_y requer ao menos 1 layer com 'image'.")

    img_a = load_image(layers[0]["image"], W, H, margin=1.0)
    img_b = load_image(layers[1]["image"], W, H, margin=1.0) if len(layers) > 1 else img_a

    def ease_out(x: float) -> float:
        return 1.0 - (1.0 - x) ** 2

    def make_frame(t: float) -> np.ndarray:
        if t < half:
            p = ease_out(t / half)
            angle = p * (math.pi / 2)
            img = img_a
        else:
            p = ease_out((t - half) / half)
            angle = (1.0 - p) * (math.pi / 2)
            img = img_b

        cos_a = max(abs(math.cos(angle)), 0.001)
        visible_w = int(W * cos_a)

        if visible_w < 2:
            return np.zeros((H, W, 3), dtype=np.uint8)

        squeezed = _resize(img, visible_w, H)
        canvas = np.zeros((H, W, 3), dtype=np.uint8)
        x_off = (W - visible_w) // 2
        canvas[:, x_off : x_off + visible_w] = squeezed

        shadow_w = max(1, int(visible_w * 0.15))
        for side in (0, 1):
            for px in range(shadow_w):
                ratio = px / shadow_w
                alpha_s = (1.0 - ratio) * 0.65
                col = x_off + px if side == 0 else x_off + visible_w - 1 - px
                if 0 <= col < W:
                    canvas[:, col] = (canvas[:, col] * (1.0 - alpha_s)).astype(np.uint8)

        return apply_fx(canvas, t, fps, W, H, overlays)

    return VideoClip(make_frame, duration=dur).with_fps(fps)
