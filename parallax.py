"""
scenes/parallax.py
Cena 'parallax': múltiplas camadas de imagem se movendo em velocidades diferentes,
criando sensação de profundidade.

Modos de uso:

1. Multi-layer (imagens separadas por profundidade):
   - Camada 0 (fundo) → mais lenta
   - Camada N (frente) → mais rápida
   - Se as imagens de frente tiverem canal alpha (PNG com transparência),
     o fundo aparece por trás delas.

2. Single-image auto-split:
   - Uma única imagem é dividida em 2 layers (fundo blur + frente nítida)
     que se movem em velocidades diferentes, simulando profundidade.

JSON de exemplo — multi-layer:
{
  "id": 3,
  "type": "parallax",
  "duration": 8.0,
  "direction": "right",
  "layers": [
    { "image": "images/bg.png",  "speed": 0.25 },
    { "image": "images/mid.png", "speed": 0.55, "alpha": 0.9 },
    { "image": "images/fg.png",  "speed": 1.00, "alpha": 0.8 }
  ],
  "overlay": ["grain", "vignette"],
  "transition_out": "crossfade"
}

JSON de exemplo — single-image (auto-split):
{
  "id": 3,
  "type": "parallax",
  "duration": 8.0,
  "images": ["images/bg.png"],
  "direction": "right",
  "pan_range": 0.12,
  "overlay": ["grain", "vignette"],
  "transition_out": "crossfade"
}

Parâmetros:
  direction   : "right" | "left" | "up" | "down" (sentido do movimento)
  pan_range   : fração da largura/altura usada como amplitude máxima de pan (default 0.12)
  layers[].speed  : multiplicador de velocidade (0 = estático, 1 = movimento máximo)
  layers[].alpha  : opacidade de composição sobre as camadas abaixo (default 1.0)
"""
import numpy as np
from PIL import Image, ImageFilter, ImageEnhance

from effects.overlays import apply_fx
from utils.image import _resize


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_layer(path: str, W: int, H: int, margin: float = 1.35) -> np.ndarray:
    """
    Carrega imagem com margem extra para o pan não expor bordas pretas.
    Preserva canal alpha se existir → retorna H×W×4 ou H×W×3.
    """
    img = Image.open(path)
    has_alpha = img.mode == "RGBA"
    img = img.convert("RGBA") if has_alpha else img.convert("RGB")

    scale = max(W / img.width, H / img.height) * margin
    nw, nh = int(img.width * scale), int(img.height * scale)
    img = img.resize((nw, nh), Image.LANCZOS)
    return np.array(img)


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


def _auto_split_layers(raw_rgb: np.ndarray, W: int, H: int, margin: float = 1.35):
    """
    Divide uma única imagem em 2 camadas (fundo blur + frente nítida)
    para o modo single-image.

    Returns:
        [(img_bg_array, speed=0.3, alpha=1.0),
         (img_fg_array, speed=1.0, alpha=0.7)]
    """
    pil = Image.fromarray(raw_rgb.astype(np.uint8))

    # Camada de fundo: blur + desaturação leve
    bg = pil.filter(ImageFilter.GaussianBlur(radius=6))
    bg = ImageEnhance.Color(bg).enhance(0.7)
    bg_arr = np.array(bg)

    # Camada de frente: nítida (usa o raw direto)
    fg_arr = raw_rgb.astype(np.uint8)

    return [
        (bg_arr, 0.30, 1.0),
        (fg_arr, 1.00, 0.75),
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
    MARGIN = 1.35  # margem extra de carga para acomodar o pan

    # ── Monta lista de layers ─────────────────────────────────────────────────
    # Formato interno: [(img_array, speed, alpha), ...]
    layers_data: list[tuple[np.ndarray, float, float]] = []

    if "layers" in scene:
        for cfg in scene["layers"]:
            img = _load_layer(cfg["image"], W, H, margin=MARGIN)
            speed = float(cfg.get("speed", 0.5))
            alpha = float(cfg.get("alpha", 1.0))
            layers_data.append((img, speed, alpha))
    else:
        # Modo single-image: auto-split
        from utils.image import load_image
        raw = load_image(scene["images"][0], W, H, margin=MARGIN)
        layers_data = _auto_split_layers(raw, W, H, MARGIN)
        # Converte de volta para arrays com margem (load_image já faz isso)
        layers_data = [
            (_load_layer(scene["images"][0], W, H, margin=MARGIN), spd, alp)
            for (_, spd, alp) in layers_data
        ]
        # Para single-image auto-split precisamos de tratamento especial
        layers_data = _build_single_image_layers(scene["images"][0], W, H, MARGIN)

    def make_frame(t: float) -> np.ndarray:
        # Progresso suavizado: 0 → 1
        p = t / max(dur, 1e-6)
        p_smooth = p * p * (3.0 - 2.0 * p)

        canvas = np.zeros((H, W, 3), dtype=np.uint8)

        for i, (img, speed, alpha) in enumerate(layers_data):
            ih, iw = img.shape[:2]

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

        return apply_fx(canvas, t, fps, W, H, overlays)

    return VideoClip(make_frame, duration=dur).with_fps(fps)


def _build_single_image_layers(
    image_path: str, W: int, H: int, margin: float
) -> list[tuple[np.ndarray, float, float]]:
    """
    Para single-image auto-split: carrega a imagem e cria 2 versões
    (bg desfocada + fg nítida) em numpy com margem para pan.
    """
    img_pil = Image.open(image_path).convert("RGB")

    scale = max(W / img_pil.width, H / img_pil.height) * margin
    nw, nh = int(img_pil.width * scale), int(img_pil.height * scale)
    img_pil = img_pil.resize((nw, nh), Image.LANCZOS)

    # Fundo: blur + desaturação
    bg_pil = img_pil.filter(ImageFilter.GaussianBlur(radius=8))
    bg_pil = ImageEnhance.Color(bg_pil).enhance(0.65)
    bg_arr = np.array(bg_pil)

    # Frente: nítida
    fg_arr = np.array(img_pil)

    return [
        (bg_arr, 0.30, 1.0),   # fundo lento
        (fg_arr, 1.00, 0.72),  # frente rápida, ligeiramente transparente
    ]
