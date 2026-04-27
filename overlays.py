"""
effects/overlays.py
Overlays de pós-processamento aplicados frame-a-frame.

Todos os efeitos são combináveis: basta incluir o nome na lista `overlay` da cena.
"""
import numpy as np

# ── Vignette ──────────────────────────────────────────────────────────────────
_VIG_CACHE: dict = {}


def _vig_mask(W: int, H: int, strength: float = 0.6) -> np.ndarray:
    """
    Máscara de vignette pré-calculada e cacheada por resolução.
    Retorna array float32 H×W×1 com valores em [0.2, 1.0].
    """
    key = (W, H, strength)
    if key not in _VIG_CACHE:
        Y, X = np.ogrid[:H, :W]
        dist = np.sqrt(
            ((X - W / 2) / (W / 2)) ** 2 + ((Y - H / 2) / (H / 2)) ** 2
        )
        mask = np.clip(1.0 - dist * strength * 0.72, 0.2, 1.0)
        _VIG_CACHE[key] = mask[:, :, np.newaxis].astype(np.float32)
    return _VIG_CACHE[key]


# ── Grain ──────────────────────────────────────────────────────────────────────
_GRAIN_CACHE: dict = {}
_GRAIN_POOL = 12  # pool de padrões pré-calculados para variar frame-a-frame


def _grain_pool(W: int, H: int, intensity: int = 16) -> list[np.ndarray]:
    """
    Pool de padrões de grão cinematográfico (luminância, 1 canal).
    Cacheado por resolução e intensidade.
    """
    key = (W, H, intensity)
    if key not in _GRAIN_CACHE:
        _GRAIN_CACHE[key] = [
            np.random.randint(-intensity, intensity + 1, (H, W, 1), dtype=np.int16)
            for _ in range(_GRAIN_POOL)
        ]
    return _GRAIN_CACHE[key]


# ── Dispatcher ─────────────────────────────────────────────────────────────────
def apply_fx(
    frame: np.ndarray,
    t: float,
    fps: int,
    W: int,
    H: int,
    overlays: list[str],
) -> np.ndarray:
    """
    Aplica todos os overlays ativos ao frame (in-place seguro — opera em cópia float).

    Args:
        frame:    array uint8 H×W×3
        t:        tempo atual em segundos
        fps:      frames por segundo do projeto
        W, H:     resolução
        overlays: lista de nomes de overlay ativos

    Returns:
        frame uint8 H×W×3 processado
    """
    out = frame.astype(np.float32)

    if "desaturate" in overlays:
        gray = out.mean(axis=2, keepdims=True)
        out = out * 0.45 + gray * 0.55

    if "vignette" in overlays:
        out *= _vig_mask(W, H)

    if "grain" in overlays:
        pool = _grain_pool(W, H)
        idx = int(t * fps) % len(pool)
        out = np.clip(out + pool[idx], 0, 255)

    return out.astype(np.uint8)
