"""
utils/image.py
Carregamento de imagem e backend de resize.
OpenCV é ~8x mais rápido que PIL para resize de frames.
"""
import numpy as np
from PIL import Image

try:
    import cv2

    def _resize(arr: np.ndarray, w: int, h: int) -> np.ndarray:
        return cv2.resize(arr, (w, h), interpolation=cv2.INTER_LINEAR)

    print("ℹ OpenCV disponível — resize acelerado ativo")

except ImportError:

    def _resize(arr: np.ndarray, w: int, h: int) -> np.ndarray:
        return np.array(Image.fromarray(arr).resize((w, h), Image.BILINEAR))

    print("ℹ OpenCV não instalado — usando PIL (mais lento)")


def load_image(
    path: str,
    W: int,
    H: int,
    margin: float = 1.18,
    bg: tuple = (12, 12, 12),
) -> np.ndarray:
    """
    Carrega imagem RGB, composta sobre fundo se tiver canal alpha,
    e redimensiona com margem extra para dar espaço ao movimento (Ken Burns / parallax).

    Args:
        path:   caminho do arquivo de imagem
        W, H:   resolução de destino
        margin: fator de escala extra além do necessário para cobrir W×H
        bg:     cor de fundo (R, G, B) usada quando a imagem tem alpha
    """
    img = Image.open(path)

    if img.mode == "RGBA":
        background = Image.new("RGB", img.size, bg)
        background.paste(img, mask=img.split()[3])
        img = background
    else:
        img = img.convert("RGB")

    scale = max(W / img.width, H / img.height) * margin
    nw = int(img.width * scale)
    nh = int(img.height * scale)
    img = img.resize((nw, nh), Image.LANCZOS)

    return np.array(img)


def load_image_rgba(
    path: str,
    W: int,
    H: int,
    margin: float = 1.18,
) -> np.ndarray:
    """
    Versão que preserva canal alpha (RGBA), útil para layers do parallax
    com transparência real.  Retorna array uint8 H×W×4.
    """
    img = Image.open(path).convert("RGBA")
    scale = max(W / img.width, H / img.height) * margin
    nw = int(img.width * scale)
    nh = int(img.height * scale)
    img = img.resize((nw, nh), Image.LANCZOS)
    return np.array(img)


def get_layer_images(scene: dict) -> list[dict]:
    """
    Extrai a lista de layers do JSON.
    Suporta novo formato (layers[]) e legado (images[]) com conversao automatica.

    Returns:
        Lista de dicts, cada um com ao menos a chave "image".
    """
    if "layers" in scene:
        return scene["layers"]
    return [
        {"image": img, "image_prompt": "", "video_prompt": ""}
        for img in scene.get("images", [])
    ]
