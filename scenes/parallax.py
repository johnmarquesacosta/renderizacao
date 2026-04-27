"""
scenes/parallax.py
Cena 'parallax': auto-split de uma unica imagem em 2 layers
(fundo blur + frente nitida), com velocidades fixas.

JSON de exemplo:
{
    "id": 3,
    "type": "parallax",
    "duration": 8.0,
    "direction": "right",
    "pan_range": 0.12,
    "layers": [
        { "image": "images/bg.png" }
    ],
    "overlay": ["grain", "vignette"],
    "transition_out": "crossfade"
}
"""
import numpy as np
from PIL import Image, ImageFilter, ImageEnhance

from effects.overlay_extras import apply_overlay_extras
from effects.overlays import apply_fx
from utils.image import get_layer_images


# ── Helpers ───────────────────────────────────────────────────────────────────

def _crop_layer(img: np.ndarray, W: int, H: int, offset_x: int, offset_y: int) -> np.ndarray:
    """
    Recorta W×H da imagem com offset, clampando nas bordas.
    Retorna H×W×C onde C é 3 (RGB) ou 4 (RGBA).
    """
    ih, iw = img.shape[:2]
    cx = max(0, min((iw - W) // 2 + offset_x, iw - W))
    cy = max(0, min((ih - H) // 2 + offset_y, ih - H))
    return img[cy : cy + H, cx : cx + W]


def _composite(canvas: np.ndarray, layer: np.ndarray, alpha: float) -> np.ndarray:
    """
    Compõe `layer` sobre `canvas`.

    - Se layer tem 4 canais: usa o canal alpha do PNG × alpha global.
    - Se layer tem 3 canais: blending simples com `alpha`.

    Retorna canvas uint8 H×W×3.
    """
    if layer.shape[2] == 4:
        layer_rgb = layer[:, :, :3].astype(np.float32)
        layer_a = (layer[:, :, 3:4].astype(np.float32) / 255.0) * alpha
        canvas = canvas.astype(np.float32) * (1.0 - layer_a) + layer_rgb * layer_a
    else:
        layer_rgb = layer.astype(np.float32)
        canvas = canvas.astype(np.float32) * (1.0 - alpha) + layer_rgb * alpha

    return np.clip(canvas, 0, 255).astype(np.uint8)


def _auto_split_layers(
    image_path: str, W: int, H: int, margin: float = 1.35
) -> list[tuple[np.ndarray, float, float]]:
    """
    Carrega a imagem e cria 2 versoes (bg desfocada + fg nitida)
    em numpy com margem para pan.
    """
    img_pil = Image.open(image_path).convert("RGB")

    scale = max(W / img_pil.width, H / img_pil.height) * margin
    nw, nh = int(img_pil.width * scale), int(img_pil.height * scale)
    img_pil = img_pil.resize((nw, nh), Image.LANCZOS)

    bg_pil = img_pil.filter(ImageFilter.GaussianBlur(radius=8))
    bg_pil = ImageEnhance.Color(bg_pil).enhance(0.65)
    bg_arr = np.array(bg_pil)
    fg_arr = np.array(img_pil)

    return [
        (bg_arr, 0.30, 1.0),
        (fg_arr, 1.00, 0.72),
    ]


# ── Builder principal ──────────────────────────────────────────────────────────

def scene_parallax(scene: dict, W: int, H: int, fps: int):
    """
    Constrói um VideoClip com efeito parallax.
    """
    from moviepy import VideoClip

    dur = float(scene["duration"])
    direction: str = scene.get("direction", "right")
    pan_range: float = float(scene.get("pan_range", 0.12))
    overlays: list = scene.get("overlay", ["grain", "vignette"])
    grain_intensity = int(scene.get("grain_intensity", 8))
    overlay_extras = scene.get("overlay_extras", [])
    MARGIN = 1.35  # margem extra de carga para acomodar o pan

    layers = get_layer_images(scene)
    if not layers:
        raise ValueError("Parallax requer ao menos 1 layer com 'image'.")
    layers_data = _auto_split_layers(layers[0]["image"], W, H, MARGIN)

    def make_frame(t: float) -> np.ndarray:
        # Progresso suavizado: 0 → 1
        p = t / max(dur, 1e-6)
        p_smooth = p * p * (3.0 - 2.0 * p)

        canvas = np.zeros((H, W, 3), dtype=np.uint8)

        for i, (img, speed, alpha) in enumerate(layers_data):
            # Deslocamento máximo proporcional ao pan_range e velocidade da layer
            max_px = int(pan_range * W * speed)
            max_py = int(pan_range * H * speed)

            if direction == "right":
                ox = int(p_smooth * max_px)
                oy = 0
            elif direction == "left":
                ox = -int(p_smooth * max_px)
                oy = 0
            elif direction == "down":
                ox = 0
                oy = int(p_smooth * max_py)
            else:  # up
                ox = 0
                oy = -int(p_smooth * max_py)

            crop = _crop_layer(img, W, H, ox, oy)

            if i == 0:
                # Primeira layer: preenche o canvas diretamente (sem blending)
                canvas = crop[:, :, :3].copy()
            else:
                canvas = _composite(canvas, crop, alpha)

        canvas = apply_fx(canvas, t, fps, W, H, overlays, grain_intensity=grain_intensity)

        if overlay_extras:
            canvas = apply_overlay_extras(
                canvas,
                t,
                overlay_extras,
                W,
                H,
                scene_seed=int(scene.get("id", 0)),
            )

        return canvas

    return VideoClip(make_frame, duration=dur).with_fps(fps)
