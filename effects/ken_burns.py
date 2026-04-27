"""
effects/ken_burns.py
Efeito Ken Burns: zoom lento + pan suave sobre um frame de imagem.

Cada preset define (zoom_inicial, zoom_final, pan_x, pan_y).
  - pan_x / pan_y em [-1, 1]: sentido e intensidade do deslocamento
  - zoom > 1 significa que a imagem precisa ter margem extra (load_image margin ≥ zoom_max)
"""
import random
import numpy as np
from utils.image import _resize

# ── Presets ────────────────────────────────────────────────────────────────────
_KB_PRESETS: dict[str, tuple[float, float, float, float]] = {
    #                       z0     z1     px     py
    "ken_burns_in":        (1.00, 1.08,  0.00,  0.00),
    "ken_burns_out":       (1.08, 1.00,  0.00,  0.00),
    "ken_burns_pan_left":  (1.04, 1.06, -0.55,  0.00),
    "ken_burns_pan_right": (1.04, 1.06,  0.55,  0.00),
    "ken_burns_up":        (1.04, 1.06,  0.00, -0.40),
    "ken_burns_down":      (1.04, 1.06,  0.00,  0.40),
    "ken_burns_drift_in":  (1.00, 1.09,  0.30,  0.15),
    "ken_burns_drift_out": (1.09, 1.00, -0.30, -0.10),
}


def resolve_kb(effect: str, seed: int = 0) -> tuple[float, float, float, float]:
    """
    Retorna (z0, z1, pan_x, pan_y) para o efeito solicitado.

    'ken_burns_random' gera uma direção determinística com base no seed
    (garante reproducibilidade entre renderizações).
    """
    if effect in _KB_PRESETS:
        return _KB_PRESETS[effect]

    # ken_burns_random — deterministico pelo seed
    rng = random.Random(seed)
    z0 = rng.choice([1.00, 1.07])
    z1 = 1.07 if z0 == 1.00 else 1.00
    px = rng.uniform(-0.45, 0.45)
    py = rng.uniform(-0.25, 0.25)
    return z0, z1, px, py


def kb_frame(
    img: np.ndarray,
    t: float,
    dur: float,
    z0: float,
    z1: float,
    px: float,
    py: float,
    W: int,
    H: int,
) -> np.ndarray:
    """
    Recorta e redimensiona um quadro da imagem aplicando Ken Burns em t.

    Args:
        img:      imagem pré-carregada (numpy H×W×3)
        t:        tempo atual em segundos
        dur:      duração total da cena
        z0, z1:   zoom inicial e final
        px, py:   direção do pan (-1.0 a 1.0)
        W, H:     resolução de saída

    Returns:
        frame numpy uint8 H×W×3
    """
    ih, iw = img.shape[:2]
    p = t / max(dur, 1e-6)
    # smoothstep: movimento suave sem arranco
    p = p * p * (3.0 - 2.0 * p)

    zoom = z0 + (z1 - z0) * p
    cw = int(W / zoom)
    ch = int(H / zoom)

    cx = iw // 2 + int(px * (iw - cw) // 2 * p)
    cy = ih // 2 + int(py * (ih - ch) // 2 * p)

    x1 = int(max(0, min(cx - cw // 2, iw - cw)))
    y1 = int(max(0, min(cy - ch // 2, ih - ch)))

    return _resize(img[y1 : y1 + ch, x1 : x1 + cw], W, H)
