"""
scenes/typewriting.py
Cena 'typewriting': texto aparece caractere a caractere sobre fundo cinematográfico.

Estrutura visual (inspirada no componente React de referência):
  ┌─────────────────────────────────────────────┐
  │  [imagem de fundo — blur + escurecida]       │
  │                                              │
  │  [imagem nítida centralizada — zoom suave]   │
  │                                              │
  │  ┃ Título sendo digitado█                    │  ← caixa no rodapé
  │    Subtítulo (aparece após título completo)  │
  └─────────────────────────────────────────────┘

JSON de exemplo:
{
  "id": 1,
  "type": "typewriting",
  "duration": 8.0,
  "text": "Construindo o futuro com tecnologia",
  "subtitle": "Uma história de inovação",
  "images": ["images/capa.png"],
  "show_center_image": true,
  "typing_start": 0.6,
  "chars_per_second": 14,
  "fade_in": 0.4,
  "bg_overlay_alpha": 0.72,
  "accent_color": [99, 102, 241],
  "font_size": 56,
  "subtitle_font_size": 32,
  "text_color": [255, 255, 255],
  "subtitle_color": [180, 180, 200],
  "overlay": ["grain"],
  "transition_out": "crossfade"
}

Notas:
  - `images` é opcional: sem imagem, o fundo fica preto sólido.
  - `show_center_image` exibe a versão nítida com zoom suave (padrão: true quando há imagem).
  - O cursor piscante '█' some quando o texto está completo.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance

from effects.overlays import apply_fx
from utils.image import _resize
from utils.text import load_font, wrap_text, text_line_height


# ── Helpers internos ──────────────────────────────────────────────────────────

def _load_bg(path: str, W: int, H: int) -> np.ndarray:
    """Carrega imagem redimensionada para cobrir W×H exatamente."""
    img = Image.open(path).convert("RGB")
    scale = max(W / img.width, H / img.height)
    nw, nh = int(img.width * scale), int(img.height * scale)
    img = img.resize((nw, nh), Image.LANCZOS)
    # Recorta centralizado
    left = (nw - W) // 2
    top = (nh - H) // 2
    return np.array(img.crop((left, top, left + W, top + H)))


def _make_blurred_bg(raw: np.ndarray, W: int, H: int, brightness: float) -> np.ndarray:
    """
    Aplica blur + escurecimento à imagem de fundo.
    Retorna array uint8 H×W×3.
    """
    pil = Image.fromarray(raw)
    # Blur forte (compensa bordas com scale ligeiro)
    pil = pil.filter(ImageFilter.GaussianBlur(radius=18))
    pil = ImageEnhance.Brightness(pil).enhance(brightness)
    return np.array(pil)


def _make_center_image(
    raw: np.ndarray,
    W: int,
    H: int,
    scale: float,
    translate_y: float = -0.08,
) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    """
    Prepara a imagem central nítida (sem blur) com escala e translação.

    Returns:
        (array_img, (x, y, w, h)) — posição de colagem no canvas
    """
    target_w = int(W * scale)
    target_h = int(H * scale)
    img = _resize(raw, target_w, target_h)

    x = (W - target_w) // 2
    y = int((H - target_h) // 2 + translate_y * H)
    return img, (x, y, target_w, target_h)


def _blend_image(canvas: np.ndarray, img: np.ndarray, x: int, y: int) -> np.ndarray:
    """Coloca `img` em `canvas` na posição (x, y), clampando bordas."""
    ih, iw = img.shape[:2]
    H, W = canvas.shape[:2]
    x1, y1 = max(0, x), max(0, y)
    x2, y2 = min(W, x + iw), min(H, y + ih)
    sx1, sy1 = x1 - x, y1 - y
    sx2, sy2 = sx1 + (x2 - x1), sy1 + (y2 - y1)
    if x2 > x1 and y2 > y1:
        canvas[y1:y2, x1:x2] = img[sy1:sy2, sx1:sx2]
    return canvas


def _render_text_box(
    canvas: np.ndarray,
    typed_text: str,
    subtitle_text: str,
    subtitle_alpha: float,
    show_cursor: bool,
    font_title,
    font_subtitle,
    W: int,
    H: int,
    accent_color: tuple,
    text_color: tuple,
    subtitle_color: tuple,
    bg_overlay_alpha: float,
    slide_y: float,
) -> np.ndarray:
    """
    Desenha a caixa de texto na parte inferior com PIL e compõe sobre o canvas.

    Args:
        slide_y: translação Y em pixels (para animação de entrada)
    """
    BOX_MAX_W = int(W * 0.70)
    PAD_X, PAD_Y = 40, 24
    BORDER_W = 6
    CORNER_R = 12
    BOTTOM_MARGIN = 80

    title_lines = wrap_text(typed_text + ("█" if show_cursor else ""), font_title, BOX_MAX_W - PAD_X * 2)
    sub_lines = wrap_text(subtitle_text, font_subtitle, BOX_MAX_W - PAD_X * 2) if subtitle_text else []

    lh_title = text_line_height(font_title) + 6
    lh_sub = text_line_height(font_subtitle) + 4

    box_h = PAD_Y * 2 + len(title_lines) * lh_title
    if sub_lines and subtitle_alpha > 0:
        box_h += 10 + len(sub_lines) * lh_sub
    box_w = BOX_MAX_W

    # Posição: canto inferior esquerdo (margem esquerda = 5% da largura)
    box_x = int(W * 0.05)
    box_y = H - BOTTOM_MARGIN - box_h + int(slide_y)

    # Cria imagem RGBA para a caixa (para composição com alpha)
    box_img = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(box_img)

    # Fundo semi-transparente
    bg_a = int(bg_overlay_alpha * 255)
    draw.rounded_rectangle(
        [BORDER_W, 0, box_w - 1, box_h - 1],
        radius=CORNER_R,
        fill=(0, 0, 0, bg_a),
    )

    # Borda esquerda colorida (accent)
    draw.rectangle([0, 0, BORDER_W - 1, box_h - 1], fill=(*accent_color, 255))

    # Título digitado
    ty = PAD_Y
    for line in title_lines:
        draw.text((PAD_X, ty), line, font=font_title, fill=(*text_color, 255))
        ty += lh_title

    # Subtítulo com fade-in
    if sub_lines and subtitle_alpha > 0:
        ty += 10
        sub_a = int(subtitle_alpha * 255)
        for line in sub_lines:
            draw.text((PAD_X, ty), line, font=font_subtitle, fill=(*subtitle_color, sub_a))
            ty += lh_sub

    # Compõe caixa sobre o canvas
    pil_canvas = Image.fromarray(canvas)
    pil_canvas.paste(box_img, (box_x, max(0, box_y)), mask=box_img.split()[3])

    return np.array(pil_canvas)


# ── Builder principal ──────────────────────────────────────────────────────────

def scene_typewriting(scene: dict, W: int, H: int, fps: int):
    """
    Constrói um VideoClip do efeito typewriting.
    """
    from moviepy import VideoClip

    dur = float(scene["duration"])
    full_text: str = scene.get("text", "")
    subtitle: str = scene.get("subtitle", "")
    images: list = scene.get("images", [])

    typing_start: float = float(scene.get("typing_start", 0.5))
    chars_per_sec: float = float(scene.get("chars_per_second", 13))
    fade_in: float = float(scene.get("fade_in", 0.35))
    bg_overlay_alpha: float = float(scene.get("bg_overlay_alpha", 0.72))
    bg_brightness: float = float(scene.get("bg_brightness", 0.35))
    show_center: bool = scene.get("show_center_image", bool(images))
    accent_color: tuple = tuple(scene.get("accent_color", [99, 102, 241]))
    text_color: tuple = tuple(scene.get("text_color", [255, 255, 255]))
    subtitle_color: tuple = tuple(scene.get("subtitle_color", [180, 180, 200]))
    font_size: int = int(scene.get("font_size", 56))
    sub_font_size: int = int(scene.get("subtitle_font_size", 32))
    overlays: list = scene.get("overlay", ["grain"])

    # Fontes
    font_title = load_font(font_size, bold=True)
    font_subtitle = load_font(sub_font_size, bold=False)

    # Pré-computação de imagens
    bg_blurred = None
    center_raw = None
    if images:
        raw = _load_bg(images[0], W, H)
        bg_blurred = _make_blurred_bg(raw, W, H, bg_brightness)
        if show_center:
            center_raw = raw  # usamos a imagem original (nítida)

    # Tempo em que o título estará completo
    typing_dur = len(full_text) / max(chars_per_sec, 1)
    title_done_at = typing_start + typing_dur
    # Subtítulo começa a aparecer quando o título está completo
    sub_fade_dur = 0.5

    def make_frame(t: float) -> np.ndarray:
        # ── Fade-in global ────────────────────────────────────────────────────
        fade = min(t / fade_in, 1.0) if fade_in > 0 else 1.0

        # ── Fundo ─────────────────────────────────────────────────────────────
        if bg_blurred is not None:
            canvas = bg_blurred.copy()
        else:
            canvas = np.zeros((H, W, 3), dtype=np.uint8)

        # ── Imagem central nítida (zoom suave) ────────────────────────────────
        if center_raw is not None and show_center:
            # Zoom cresce de 0.72 → 0.80 ao longo da cena
            img_scale = 0.72 + 0.08 * (t / dur)
            center_img, (cx, cy, cw, ch) = _make_center_image(
                center_raw, W, H, scale=img_scale
            )
            canvas = _blend_image(canvas, center_img, cx, cy)

        # ── Texto digitado ────────────────────────────────────────────────────
        if t >= typing_start:
            elapsed = t - typing_start
            n_chars = int(elapsed * chars_per_sec)
            typed = full_text[:n_chars]
            typing_complete = n_chars >= len(full_text)

            # Cursor pisca a 2Hz quando ainda digitando
            blink_on = (int(t * 2) % 2 == 0)
            show_cursor = not typing_complete and blink_on

            # Subtítulo: fade-in após título completo
            sub_alpha = 0.0
            if typing_complete and subtitle:
                sub_elapsed = t - title_done_at
                sub_alpha = min(sub_elapsed / sub_fade_dur, 1.0)

            # Slide up: caixa entra deslizando do rodapé (nos primeiros 0.3s após typing_start)
            slide_progress = min((t - typing_start) / 0.3, 1.0)
            slide_ease = 1.0 - (1.0 - slide_progress) ** 3
            slide_y = (1.0 - slide_ease) * 60  # 60px para cima

            canvas = _render_text_box(
                canvas,
                typed_text=typed,
                subtitle_text=subtitle if typing_complete else "",
                subtitle_alpha=sub_alpha,
                show_cursor=show_cursor,
                font_title=font_title,
                font_subtitle=font_subtitle,
                W=W,
                H=H,
                accent_color=accent_color,
                text_color=text_color,
                subtitle_color=subtitle_color,
                bg_overlay_alpha=bg_overlay_alpha,
                slide_y=slide_y,
            )

        # ── Overlays cinematográficos ─────────────────────────────────────────
        canvas = apply_fx(canvas, t, fps, W, H, overlays)

        # ── Fade-in global: multiplica por alpha ──────────────────────────────
        if fade < 1.0:
            canvas = (canvas * fade).astype(np.uint8)

        return canvas

    return VideoClip(make_frame, duration=dur).with_fps(fps)
