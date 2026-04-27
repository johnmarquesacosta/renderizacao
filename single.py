"""
scenes/single.py
Cena 'single': uma imagem com efeito Ken Burns + overlays.

JSON de exemplo:
{
  "id": 1,
  "type": "single",
  "duration": 5.0,
  "images": ["images/scene_1.png"],
  "effect": "ken_burns_in",
  "overlay": ["grain", "vignette"],
  "transition_out": "crossfade"
}
"""
import numpy as np
from effects.ken_burns import kb_frame, resolve_kb
from effects.overlays import apply_fx
from utils.image import load_image


def scene_single(scene: dict, W: int, H: int, fps: int):
    """
    Constrói um VideoClip de cena simples (uma imagem, Ken Burns, overlays).
    """
    from moviepy import VideoClip  # import local evita dependência circular

    dur = float(scene["duration"])
    img = load_image(scene["images"][0], W, H)
    z0, z1, px, py = resolve_kb(
        scene.get("effect", "ken_burns_random"),
        seed=scene.get("id", 0),
    )
    overlays = scene.get("overlay", ["grain", "vignette"])

    def make_frame(t: float) -> np.ndarray:
        f = kb_frame(img, t, dur, z0, z1, px, py, W, H)
        return apply_fx(f, t, fps, W, H, overlays)

    return VideoClip(make_frame, duration=dur).with_fps(fps)
