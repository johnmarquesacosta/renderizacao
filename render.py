#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║  render.py  —  Motor de Renderização de Vídeo               ║
║  Lê project.json e gera o vídeo final com efeitos dinâmicos  ║
║                                                              ║
║  Uso: python render.py project.json                          ║
╚══════════════════════════════════════════════════════════════╝
"""

import json
import sys
import os
import random
import importlib

import numpy as np
from PIL import Image

# ── resize backend: opencv é ~8x mais rápido que PIL ──────────
try:
    import cv2
    def _resize(arr: np.ndarray, w: int, h: int) -> np.ndarray:
        return cv2.resize(arr, (w, h), interpolation=cv2.INTER_LINEAR)
    print("ℹ  OpenCV disponível — resize acelerado ativo")
except ImportError:
    def _resize(arr: np.ndarray, w: int, h: int) -> np.ndarray:
        return np.array(Image.fromarray(arr).resize((w, h), Image.BILINEAR))
    print("ℹ  OpenCV não instalado — usando PIL (mais lento)")

try:
    _moviepy = importlib.import_module("moviepy.editor")
except ModuleNotFoundError:
    _moviepy = importlib.import_module("moviepy")

VideoClip = _moviepy.VideoClip
AudioFileClip = _moviepy.AudioFileClip
concatenate_videoclips = _moviepy.concatenate_videoclips


# ══════════════════════════════════════════════════════════════
#  CARREGAMENTO DE IMAGEM
# ══════════════════════════════════════════════════════════════

def load_image(path: str, W: int, H: int, margin: float = 1.18,
               bg: tuple = (12, 12, 12)) -> np.ndarray:
    """
    Carrega imagem, composta sobre fundo se tiver canal alpha,
    e redimensiona com margem extra para dar espaço ao Ken Burns.
    """
    img = Image.open(path)

    if img.mode == "RGBA":
        background = Image.new("RGB", img.size, bg)
        background.paste(img, mask=img.split()[3])
        img = background
    else:
        img = img.convert("RGB")

    scale = max(W / img.width, H / img.height) * margin
    nw, nh = int(img.width * scale), int(img.height * scale)
    img = img.resize((nw, nh), Image.LANCZOS)
    return np.array(img)


# ══════════════════════════════════════════════════════════════
#  EFEITOS DE QUADRO (frame-level)
# ══════════════════════════════════════════════════════════════

def kb_frame(img: np.ndarray, t: float, dur: float,
              z0: float, z1: float,
              px: float, py: float,
              W: int, H: int) -> np.ndarray:
    """
    Ken Burns: recorta e redimensiona um quadro da imagem em t.
      z0/z1  — zoom inicial/final (ex: 1.0 → 1.08)
      px/py  — direção do pan  (-1.0 a 1.0)
    """
    ih, iw = img.shape[:2]
    p = t / max(dur, 1e-6)
    p = p * p * (3.0 - 2.0 * p)          # smoothstep — movimento suave

    zoom  = z0 + (z1 - z0) * p
    cw    = int(W / zoom)
    ch    = int(H / zoom)

    cx = iw // 2 + int(px * (iw - cw) // 2 * p)
    cy = ih // 2 + int(py * (ih - ch) // 2 * p)
    x1 = int(max(0, min(cx - cw // 2, iw - cw)))
    y1 = int(max(0, min(cy - ch // 2, ih - ch)))

    return _resize(img[y1:y1 + ch, x1:x1 + cw], W, H)


# ── Vignette: pré-calculado por resolução ─────────────────────
_VIG_CACHE: dict = {}

def _vig_mask(W: int, H: int, strength: float = 0.6) -> np.ndarray:
    key = (W, H, strength)
    if key not in _VIG_CACHE:
        Y, X   = np.ogrid[:H, :W]
        dist   = np.sqrt(((X - W / 2) / (W / 2)) ** 2 +
                          ((Y - H / 2) / (H / 2)) ** 2)
        mask   = np.clip(1.0 - dist * strength * 0.72, 0.2, 1.0)
        _VIG_CACHE[key] = mask[:, :, np.newaxis].astype(np.float32)
    return _VIG_CACHE[key]


# ── Grain: pool de padrões pré-calculados ─────────────────────
_GRAIN_CACHE: dict = {}
_GRAIN_POOL   = 12   # quantos padrões distintos de grão

def _grain_pool(W: int, H: int, intensity: int = 16) -> list:
    key = (W, H, intensity)
    if key not in _GRAIN_CACHE:
        # grão luminância (1 canal, broadcast nos 3)
        _GRAIN_CACHE[key] = [
            np.random.randint(-intensity, intensity + 1,
                               (H, W, 1), dtype=np.int16)
            for _ in range(_GRAIN_POOL)
        ]
    return _GRAIN_CACHE[key]


def apply_fx(frame: np.ndarray, t: float, fps: int,
              W: int, H: int, overlays: list) -> np.ndarray:
    """Aplica todos os overlays de pós-processamento ao quadro."""
    out = frame.astype(np.float32)

    if "desaturate" in overlays:
        gray = out.mean(axis=2, keepdims=True)
        out  = out * 0.45 + gray * 0.55

    if "vignette" in overlays:
        out *= _vig_mask(W, H)

    if "grain" in overlays:
        pool = _grain_pool(W, H)
        idx  = int(t * fps) % len(pool)
        out  = np.clip(out + pool[idx], 0, 255)

    return out.astype(np.uint8)


# ══════════════════════════════════════════════════════════════
#  PRESETS DE KEN BURNS
# ══════════════════════════════════════════════════════════════

_KB_PRESETS = {
    "ken_burns_in":         (1.00, 1.08,  0.0,   0.0),
    "ken_burns_out":        (1.08, 1.00,  0.0,   0.0),
    "ken_burns_pan_left":   (1.04, 1.06, -0.55,  0.0),
    "ken_burns_pan_right":  (1.04, 1.06,  0.55,  0.0),
    "ken_burns_up":         (1.04, 1.06,  0.0,  -0.4),
    "ken_burns_down":       (1.04, 1.06,  0.0,   0.4),
    "ken_burns_drift_in":   (1.00, 1.09,  0.3,   0.15),
    "ken_burns_drift_out":  (1.09, 1.00, -0.3,  -0.1),
}

def resolve_kb(effect: str, seed: int = 0) -> tuple:
    """
    Retorna (z0, z1, pan_x, pan_y).
    'ken_burns_random' gera direção determinística pelo seed.
    """
    if effect in _KB_PRESETS:
        return _KB_PRESETS[effect]

    rng = random.Random(seed)
    z0  = rng.choice([1.00, 1.07])
    z1  = 1.07 if z0 == 1.00 else 1.00
    px  = rng.uniform(-0.45, 0.45)
    py  = rng.uniform(-0.25, 0.25)
    return z0, z1, px, py


# ══════════════════════════════════════════════════════════════
#  BUILDERS DE CENA
# ══════════════════════════════════════════════════════════════

def scene_single(scene: dict, W: int, H: int, fps: int) -> VideoClip:
    """
    Cena simples: uma imagem com Ken Burns + overlays.
    """
    dur       = float(scene["duration"])
    img       = load_image(scene["images"][0], W, H)
    z0, z1, px, py = resolve_kb(
        scene.get("effect", "ken_burns_random"),
        seed=scene.get("id", 0)
    )
    overlays  = scene.get("overlay", ["grain", "vignette"])

    def make_frame(t):
        f = kb_frame(img, t, dur, z0, z1, px, py, W, H)
        return apply_fx(f, t, fps, W, H, overlays)

    return VideoClip(make_frame, duration=dur).with_fps(fps)


def scene_mosaic(scene: dict, W: int, H: int, fps: int) -> VideoClip:
    """
    Mosaico: imagens aparecem sequencialmente, deslizando de baixo para cima,
    lado a lado — ideal para "usei React, Postgres, Express, Node" → 4 ícones.

    Cada slot é portrait (slot_w × H), e juntos compõem o frame 16:9.
    """
    dur      = float(scene["duration"])
    paths    = scene["images"]
    n        = len(paths)
    interval = float(scene.get("appear_interval", dur / (n + 1.5)))
    slide_t  = float(scene.get("slide_duration", 0.42))
    overlays = scene.get("overlay", ["grain"])
    bg       = tuple(scene.get("bg_color", [12, 12, 12]))

    slot_w   = W // n
    slot_h   = H
    scene_id = scene.get("id", 0)

    # Pré-carrega imagens e configs Ken Burns (determinístico por seed)
    slots = []
    for i, path in enumerate(paths):
        img = load_image(path, slot_w, slot_h)
        z0, z1, px, py = resolve_kb("ken_burns_random",
                                      seed=scene_id * 1000 + i)
        slots.append((img, z0, z1, px, py))

    def make_frame(t):
        canvas = np.full((H, W, 3), bg, dtype=np.uint8)

        for i, (img, z0, z1, px, py) in enumerate(slots):
            t_appear = i * interval
            if t < t_appear:
                continue

            lt  = t - t_appear
            raw = min(lt / slide_t, 1.0)
            p   = 1.0 - (1.0 - raw) ** 3        # ease-out cúbico

            frame  = kb_frame(img, lt, dur, z0, z1, px, py, slot_w, slot_h)
            x0     = i * slot_w
            y_top  = int((1.0 - p) * H)          # desliza de H → 0
            vis    = H - y_top

            if vis > 0:
                canvas[y_top:H, x0:x0 + slot_w] = frame[:vis]

        return apply_fx(canvas, t, fps, W, H, overlays)

    return VideoClip(make_frame, duration=dur).with_fps(fps)


# ── Dispatcher ────────────────────────────────────────────────

_BUILDERS = {
    "single": scene_single,
    "mosaic": scene_mosaic,
}

def build_scene(scene: dict, W: int, H: int, fps: int) -> VideoClip:
    t = scene.get("type", "single")
    builder = _BUILDERS.get(t)
    if not builder:
        raise ValueError(
            f"Tipo de cena desconhecido: '{t}'. "
            f"Disponíveis: {list(_BUILDERS)}"
        )
    return builder(scene, W, H, fps)


# ══════════════════════════════════════════════════════════════
#  MONTAGEM COM TRANSIÇÕES
# ══════════════════════════════════════════════════════════════

def assemble(clips: list, scenes: list,
              default_trans: str, trans_dur: float) -> VideoClip:
    """
    Concatena clipes com transições.
    Atualmente suporta: crossfade
    """
    if len(clips) == 1:
        return clips[0]

    processed = []
    for i, clip in enumerate(clips):
        trans = scenes[i].get("transition_out", default_trans)
        if trans == "crossfade":
            try:
                from moviepy.video.fx.CrossFadeIn import CrossFadeIn
                from moviepy.video.fx.CrossFadeOut import CrossFadeOut
                if i > 0:
                    clip = clip.with_effects([CrossFadeIn(trans_dur)])
                if i < len(clips) - 1:
                    clip = clip.with_effects([CrossFadeOut(trans_dur)])
            except ImportError:
                if i > 0:
                    clip = clip.crossfadein(trans_dur)
                if i < len(clips) - 1:
                    clip = clip.crossfadeout(trans_dur)
        processed.append(clip)

    return concatenate_videoclips(
        processed,
        padding=-trans_dur,
        method="compose"
    )


# ══════════════════════════════════════════════════════════════
#  PONTO DE ENTRADA
# ══════════════════════════════════════════════════════════════

def render(project_path: str) -> None:
    with open(project_path, encoding="utf-8") as f:
        proj = json.load(f)

    fps    = proj.get("fps", 30)
    W, H   = proj.get("resolution", [1920, 1080])
    output = proj.get("output", "output.mp4")
    scenes = proj["scenes"]

    tc         = proj.get("transitions", {})
    def_trans  = tc.get("default", "crossfade")
    trans_dur  = float(tc.get("duration", 0.5))

    dur_est = sum(s.get("duration", 4) for s in scenes)
    print(f"\n🎬  {proj.get('title', 'Vídeo')}")
    print(f"    {len(scenes)} cenas  |  {W}×{H} @ {fps}fps  "
          f"|  ~{dur_est/60:.1f} min estimado\n")

    clips = []
    for i, scene in enumerate(scenes):
        label = (f"  [{i+1:3d}/{len(scenes)}] "
                 f"type={scene['type']:<7s} "
                 f"dur={scene.get('duration','?')}s  "
                 f"imgs={len(scene['images'])}")
        print(label, end="\r", flush=True)
        clips.append(build_scene(scene, W, H, fps))

    print(f"\n\n🔗  Montando {len(clips)} cenas com transições ({def_trans})...")
    final = assemble(clips, scenes, def_trans, trans_dur)

    audio_path = proj.get("audio")
    if audio_path and os.path.exists(audio_path):
        print(f"🔊  Áudio: {audio_path}")
        audio = AudioFileClip(audio_path)
        min_dur = min(audio.duration, final.duration)
        audio   = audio.subclipped(0, min_dur)
        final   = final.subclipped(0, min_dur).with_audio(audio)
    else:
        if audio_path:
            print(f"⚠  Áudio não encontrado: {audio_path}")

    print(f"💾  Escrevendo → {output}")
    final.write_videofile(
        output,
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        threads=4,
        logger="bar",
    )
    print(f"\n✅  Concluído!  →  {output}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python render.py project.json")
        sys.exit(1)
    render(sys.argv[1])
