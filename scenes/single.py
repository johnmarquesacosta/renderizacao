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
from PIL import Image, ImageDraw, ImageFont

from effects.ken_burns import kb_frame, resolve_kb
from effects.overlay_extras import apply_overlay_extras
from effects.overlays import apply_fx
from utils.image import get_layer_images, load_image
from utils.text import load_font

try:
    import cv2
except Exception:  # pragma: no cover - opcional em runtime
    cv2 = None


_FONT_CACHE: dict[tuple[str | None, int], ImageFont.ImageFont] = {}


def _get_font(font_path: str | None, size: int) -> ImageFont.ImageFont:
    key = (font_path, int(size))
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]

    if font_path:
        try:
            font = ImageFont.truetype(font_path, size)
            _FONT_CACHE[key] = font
            return font
        except Exception:
            pass

    # Usa fallback cross-platform do projeto para manter tamanho legível.
    font = load_font(size=size, bold=True)

    _FONT_CACHE[key] = font
    return font


def _resolve_text_position(position: str, W: int, H: int, tw: int, th: int, padding: int) -> tuple[int, int]:
    if "left" in position:
        x = padding
    elif "right" in position:
        x = W - tw - padding
    else:
        x = (W - tw) // 2

    if "top" in position:
        y = padding
    elif position == "center":
        y = (H - th) // 2
    else:
        y = H - th - padding

    return x, y


def draw_text_overlay(frame: np.ndarray, t: float, text_cfg: dict, W: int, H: int) -> np.ndarray:
    content = str(text_cfg.get("content", "")).strip()
    if not content:
        return frame

    position = text_cfg.get("position", "bottom_center")
    font_size = int(text_cfg.get("font_size", 60))
    color = tuple(text_cfg.get("color", [255, 255, 255]))
    font_path = text_cfg.get("font")
    padding = int(text_cfg.get("padding", 40))
    animate = text_cfg.get("animate", "fade_slide_up")
    anim_dur = float(text_cfg.get("animate_duration", 0.5))
    shadow = bool(text_cfg.get("shadow", True))
    highlight_cfg = text_cfg.get("highlight", {})

    font = _get_font(font_path, font_size)

    p_anim = min(t / max(anim_dur, 1e-6), 1.0)
    p_anim = p_anim * p_anim * (3.0 - 2.0 * p_anim)

    if animate == "none":
        alpha = 1.0
        dy = 0
    elif animate == "fade_in":
        alpha = p_anim
        dy = 0
    elif animate == "fade_slide_down":
        alpha = p_anim
        dy = -int((1.0 - p_anim) * 40)
    else:  # fade_slide_up padrão
        alpha = p_anim
        dy = int((1.0 - p_anim) * 40)

    if alpha < 0.01:
        return frame

    img = Image.fromarray(frame).convert("RGBA")
    hl_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    txt_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_measure = ImageDraw.Draw(txt_layer)

    bbox = draw_measure.textbbox((0, 0), content, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    x, y = _resolve_text_position(position, W, H, tw, th, padding)
    y += dy

    if isinstance(highlight_cfg, dict) and highlight_cfg.get("enabled", False):
        hl_color = tuple(highlight_cfg.get("color", [255, 220, 0]))
        hl_alpha = int(255 * float(highlight_cfg.get("alpha", 0.35)) * alpha)
        hl_pad = highlight_cfg.get("padding", [4, 10])
        if isinstance(hl_pad, list) and len(hl_pad) >= 2:
            hl_pad_y, hl_pad_x = int(hl_pad[0]), int(hl_pad[1])
        else:
            hl_pad_y, hl_pad_x = 4, 10

        draw_hl = ImageDraw.Draw(hl_layer)
        draw_hl.rectangle(
            [x - hl_pad_x, y - hl_pad_y, x + tw + hl_pad_x, y + th + hl_pad_y],
            fill=(*hl_color, hl_alpha),
        )

    draw_txt = ImageDraw.Draw(txt_layer)
    if shadow:
        draw_txt.text((x + 2, y + 2), content, font=font, fill=(0, 0, 0, int(160 * alpha)))
    draw_txt.text((x, y), content, font=font, fill=(*color, int(255 * alpha)))

    composed = Image.alpha_composite(img, hl_layer)
    composed = Image.alpha_composite(composed, txt_layer)
    return np.array(composed.convert("RGB"))


def tilt_y_frame(
    frame: np.ndarray,
    t: float,
    dur: float,
    max_angle_deg: float,
    W: int,
    H: int,
) -> np.ndarray:
    if cv2 is None:
        return frame

    limited_deg = max(-10.0, min(10.0, float(max_angle_deg)))

    p = t / max(dur, 1e-6)
    p = p * p * (3.0 - 2.0 * p)
    angle_rad = np.deg2rad(limited_deg * np.sin(p * np.pi))
    shift = int(W * np.tan(angle_rad) * 0.3)

    src = np.float32([[0, 0], [W, 0], [W, H], [0, H]])
    dst = np.float32([[shift, 0], [W - shift, 0], [W, H], [0, H]])

    mat = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(
        frame,
        mat,
        (W, H),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
    )


def scene_single(scene: dict, W: int, H: int, fps: int):
    """
    Constrói um VideoClip de cena simples (uma imagem, Ken Burns, overlays).
    """
    from moviepy import VideoClip  # import local evita dependência circular

    dur = float(scene["duration"])
    layers = get_layer_images(scene)
    img = load_image(layers[0]["image"], W, H)
    z0, z1, px, py = resolve_kb(
        scene.get("effect", "ken_burns_random"),
        seed=scene.get("id", 0),
    )
    overlays = scene.get("overlay", ["grain", "vignette"])
    grain_intensity = int(scene.get("grain_intensity", 8))
    overlay_extras = scene.get("overlay_extras", [])
    text_cfg = scene.get("text")
    use_tilt_y = bool(scene.get("tilt_y", False))
    tilt_max = float(scene.get("tilt_y_degrees", 6.0))

    def make_frame(t: float) -> np.ndarray:
        f = kb_frame(img, t, dur, z0, z1, px, py, W, H)
        if use_tilt_y:
            f = tilt_y_frame(f, t, dur, max_angle_deg=tilt_max, W=W, H=H)

        f = apply_fx(f, t, fps, W, H, overlays, grain_intensity=grain_intensity)

        if overlay_extras:
            f = apply_overlay_extras(
                f,
                t,
                overlay_extras,
                W,
                H,
                scene_seed=int(scene.get("id", 0)),
            )

        if isinstance(text_cfg, dict):
            f = draw_text_overlay(f, t, text_cfg, W, H)

        return f

    return VideoClip(make_frame, duration=dur).with_fps(fps)
