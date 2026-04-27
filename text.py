"""
utils/text.py
Helpers para renderização de texto: carregamento de fontes e quebra de linha.
"""
from pathlib import Path
from PIL import ImageFont

# Caminhos de fontes comuns em Linux / macOS / Windows
_BOLD_CANDIDATES = [
    # Ubuntu / Debian
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    # macOS
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    # Windows
    "C:/Windows/Fonts/arialbd.ttf",
]

_REGULAR_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "C:/Windows/Fonts/arial.ttf",
]


def _find_font(candidates: list[str]) -> str | None:
    for p in candidates:
        if Path(p).exists():
            return p
    return None


def load_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    """
    Carrega a melhor fonte disponível no sistema.

    Args:
        size: tamanho em pontos
        bold: preferir variante negrito

    Returns:
        FreeTypeFont (ou fonte padrão PIL como fallback)
    """
    candidates = _BOLD_CANDIDATES if bold else _REGULAR_CANDIDATES
    path = _find_font(candidates) or _find_font(_REGULAR_CANDIDATES + _BOLD_CANDIDATES)

    if path:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass

    # Fallback: fonte embutida do PIL (sem antialiasing, mas funciona)
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """
    Quebra `text` em linhas que cabem dentro de `max_width` pixels.

    Args:
        text:      texto a quebrar
        font:      fonte PIL para medir largura
        max_width: largura máxima em pixels

    Returns:
        lista de strings, uma por linha
    """
    words = text.split()
    lines: list[str] = []
    current: list[str] = []

    for word in words:
        test = " ".join(current + [word])
        try:
            bbox = font.getbbox(test)
            width = bbox[2] - bbox[0]
        except AttributeError:
            width = font.getlength(test)

        if width > max_width and current:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)

    if current:
        lines.append(" ".join(current))

    return lines or [""]


def text_line_height(font: ImageFont.FreeTypeFont) -> int:
    """Altura de uma linha de texto em pixels."""
    try:
        asc, desc = font.getmetrics()
        return asc + abs(desc)
    except AttributeError:
        bbox = font.getbbox("Ag")
        return bbox[3] - bbox[1]
