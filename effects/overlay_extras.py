"""
effects/overlay_extras.py
Overlays extras paramétricos por cena.

Suporta:
- particles: esferas animadas (NumPy + PIL)
- petals: pétalas PNG RGBA (ou fallback elipse) com rotação e deriva senoidal
"""
from __future__ import annotations

import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

_PETAL_CACHE: dict[str, Image.Image] = {}


def _init_particles(count: int, W: int, H: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    return [
        {
            "x": rng.uniform(0, W),
            "y": rng.uniform(0, H),
            "vy": rng.uniform(0.5, 2.0),
            "vx": rng.uniform(-0.3, 0.3),
            "size": rng.randint(2, 5),
            "phase": rng.uniform(0, math.tau),
        }
        for _ in range(max(0, count))
    ]


def _init_petals(count: int, W: int, H: int, seed: int, size_range: list[int]) -> list[dict]:
    rng = random.Random(seed)
    min_size, max_size = 20, 50
    if len(size_range) >= 2:
        min_size = int(min(size_range[0], size_range[1]))
        max_size = int(max(size_range[0], size_range[1]))

    return [
        {
            "x": rng.uniform(0, W),
            "y": rng.uniform(-H * 0.2, H),
            "vy": rng.uniform(0.8, 2.5),
            "vx": rng.uniform(-1.0, 1.0),
            "size": rng.randint(max(1, min_size), max(1, max_size)),
            "rot": rng.uniform(0, 360),
            "rot_speed": rng.uniform(-2, 2),
            "drift_phase": rng.uniform(0, math.tau),
            "drift_amp": rng.uniform(0.2, 0.8),
        }
        for _ in range(max(0, count))
    ]


def _load_petal_image(path: str | None) -> Image.Image | None:
    if not path:
        return None

    key = str(path)
    if key in _PETAL_CACHE:
        return _PETAL_CACHE[key]

    p = Path(path)
    if not p.exists():
        return None

    try:
        img = Image.open(p).convert("RGBA")
    except Exception:
        return None

    _PETAL_CACHE[key] = img
    return img


def render_particles(
    frame: np.ndarray,
    t: float,
    cfg: dict,
    W: int,
    H: int,
    scene_seed: int,
) -> np.ndarray:
    count = int(cfg.get("count", 60))
    color = tuple(cfg.get("color", [255, 255, 255]))
    speed = float(cfg.get("speed", 1.0))
    alpha = float(cfg.get("alpha", 0.5))

    particles = _init_particles(count, W, H, seed=scene_seed)

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    for p in particles:
        y = (p["y"] + t * p["vy"] * speed * 30.0) % H
        x = (p["x"] + t * p["vx"] * speed * 30.0 + math.sin(t * 1.5 + p["phase"]) * 8.0) % W
        r = int(p["size"])
        a = int(255 * max(0.0, min(alpha, 1.0)))
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(*color, a))

    img = Image.fromarray(frame).convert("RGBA")
    return np.array(Image.alpha_composite(img, overlay).convert("RGB"))


def _fallback_petal(size: int, alpha: float) -> Image.Image:
    petal = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(petal)
    d.ellipse([0, size // 4, size, size * 3 // 4], fill=(255, 180, 200, int(255 * alpha)))
    return petal


def render_petals(
    frame: np.ndarray,
    t: float,
    cfg: dict,
    W: int,
    H: int,
    scene_seed: int,
    petal_img: Image.Image | None,
) -> np.ndarray:
    count = int(cfg.get("count", 25))
    speed = float(cfg.get("speed", 0.5))
    alpha = float(cfg.get("alpha", 0.75))
    size_range = cfg.get("size_range", [20, 50])
    drift = float(cfg.get("drift", 0.4))
    do_rotate = bool(cfg.get("rotate", True))

    petals = _init_petals(count, W, H, scene_seed, size_range)
    base = Image.fromarray(frame).convert("RGBA")

    for p in petals:
        y = (p["y"] + t * p["vy"] * speed * 30.0) % max(1, int(H * 1.2))
        x = (
            p["x"]
            + t * p["vx"] * speed * 30.0
            + math.sin(t * 0.8 + p["drift_phase"]) * drift * 30.0
        ) % W

        sz = int(p["size"])
        if petal_img is not None:
            petal = petal_img.resize((sz, sz), Image.LANCZOS).convert("RGBA")
        else:
            petal = _fallback_petal(sz, alpha)

        if do_rotate:
            angle = (p["rot"] + t * p["rot_speed"] * 30.0) % 360
            petal = petal.rotate(angle, expand=True)

        r, g, b, a = petal.split()
        a = a.point(lambda v: int(v * max(0.0, min(alpha, 1.0))))
        petal = Image.merge("RGBA", (r, g, b, a))

        px, py = int(x - petal.width // 2), int(y - petal.height // 2)
        base.paste(petal, (px, py), petal)

    return np.array(base.convert("RGB"))


def apply_overlay_extras(
    frame: np.ndarray,
    t: float,
    extras: list,
    W: int,
    H: int,
    scene_seed: int = 0,
) -> np.ndarray:
    out = frame
    for idx, cfg in enumerate(extras):
        if not isinstance(cfg, dict):
            continue

        otype = cfg.get("type")
        seed = int(scene_seed) * 1000 + idx

        if otype == "particles":
            out = render_particles(out, t, cfg, W, H, seed)
        elif otype == "petals":
            petal_img = _load_petal_image(cfg.get("image"))
            out = render_petals(out, t, cfg, W, H, seed, petal_img)

    return out
