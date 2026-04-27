"""
scenes/text_highlight.py
Cena 'text_highlight': texto com marca-texto animado.
"""
import numpy as np
from PIL import Image, ImageDraw

from effects.overlay_extras import apply_overlay_extras
from effects.overlays import apply_fx
from utils.image import get_layer_images
from utils.text import load_font, text_line_height


def _load_bg(path: str, W: int, H: int) -> np.ndarray:
    """Carrega imagem redimensionada para cobrir W×H exatamente."""
    img = Image.open(path).convert("RGB")
    scale = max(W / img.width, H / img.height)
    nw, nh = int(img.width * scale), int(img.height * scale)
    img = img.resize((nw, nh), Image.LANCZOS)
    left = (nw - W) // 2
    top = (nh - H) // 2
    return np.array(img.crop((left, top, left + W, top + H)))


def scene_text_highlight(scene: dict, W: int, H: int, fps: int):
    """Constroi um VideoClip com texto e marca-texto animado."""
    from moviepy import VideoClip

    dur = float(scene["duration"])
    lines_cfg = scene["lines"]
    font_size = int(scene.get("font_size", 64))
    text_color = tuple(scene.get("text_color", [255, 255, 255]))
    hl_alpha = float(scene.get("highlight_alpha", 0.55))
    hl_dur = float(scene.get("highlight_duration", 0.6))
    start_delay = float(scene.get("start_delay", 0.8))
    line_gap_t = float(scene.get("line_gap", 1.0))
    bg_alpha = float(scene.get("bg_overlay_alpha", 0.75))
    fade_in = float(scene.get("fade_in", 0.3))
    overlays = scene.get("overlay", ["grain"])
    grain_intensity = int(scene.get("grain_intensity", 8))
    overlay_extras = scene.get("overlay_extras", [])

    font = load_font(font_size, bold=True)
    lh = text_line_height(font) + 12

    layers = get_layer_images(scene)
    bg_img = _load_bg(layers[0]["image"], W, H) if layers else None

    total_h = len(lines_cfg) * lh
    y_start = (H - total_h) // 2
    line_positions = [y_start + i * lh for i in range(len(lines_cfg))]

    line_widths = []
    for cfg in lines_cfg:
        try:
            bbox = font.getbbox(cfg["text"])
            line_widths.append(bbox[2] - bbox[0])
        except AttributeError:
            line_widths.append(int(font.getlength(cfg["text"])))

    hl_line_starts = {}
    hl_counter = 0
    for i, cfg in enumerate(lines_cfg):
        if cfg.get("highlight"):
            hl_line_starts[i] = start_delay + hl_counter * line_gap_t
            hl_counter += 1

    def make_frame(t: float) -> np.ndarray:
        fade = min(t / fade_in, 1.0) if fade_in > 0 else 1.0

        if bg_img is not None:
            base = bg_img.copy()
        else:
            base = np.zeros((H, W, 3), dtype=np.uint8)

        pil = Image.fromarray(base).convert("RGBA")
        overlay_layer = Image.new("RGBA", (W, H), (0, 0, 0, int(bg_alpha * 255)))
        pil = Image.alpha_composite(pil, overlay_layer).convert("RGB")

        hl_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        text_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw_hl = ImageDraw.Draw(hl_layer, "RGBA")
        draw_text = ImageDraw.Draw(text_layer, "RGBA")

        for i, cfg in enumerate(lines_cfg):
            text = cfg["text"]
            y = line_positions[i]
            is_hl = cfg.get("highlight", False)

            try:
                bbox = font.getbbox(text)
                tw = bbox[2] - bbox[0]
            except AttributeError:
                tw = int(font.getlength(text))

            x_text = (W - tw) // 2

            if is_hl and i in hl_line_starts:
                t_start = hl_line_starts[i]
                if t >= t_start:
                    p_sweep = min((t - t_start) / hl_dur, 1.0)
                    p_sweep = 1.0 - (1.0 - p_sweep) ** 2

                    sweep_w = int(tw * p_sweep)
                    hl_color = tuple(cfg.get("highlight_color", [255, 210, 0]))

                    pad = 8
                    rect = [
                        x_text - pad,
                        y - pad // 2,
                        x_text - pad + sweep_w + pad * 2,
                        y + lh - pad // 2,
                    ]
                    draw_hl.rectangle(rect, fill=(*hl_color, int(hl_alpha * 255)))
                    draw_text.text((x_text, y), text, font=font, fill=(*text_color, 255))
                else:
                    draw_text.text((x_text, y), text, font=font, fill=(*text_color, 255))
            else:
                draw_text.text((x_text, y), text, font=font, fill=(*text_color, 255))

        pil = Image.alpha_composite(pil.convert("RGBA"), hl_layer)
        pil = Image.alpha_composite(pil, text_layer)
        frame = np.array(pil.convert("RGB"))
        frame = apply_fx(frame, t, fps, W, H, overlays, grain_intensity=grain_intensity)

        if overlay_extras:
            frame = apply_overlay_extras(
                frame,
                t,
                overlay_extras,
                W,
                H,
                scene_seed=int(scene.get("id", 0)),
            )

        if fade < 1.0:
            frame = (frame * fade).astype(np.uint8)

        return frame

    return VideoClip(make_frame, duration=dur).with_fps(fps)
