"""
scenes/__init__.py
Registro central de todos os tipos de cena.

Para adicionar um novo tipo:
  1. Crie scenes/meu_tipo.py com uma função scene_meu_tipo(scene, W, H, fps)
  2. Importe e registre em _BUILDERS abaixo.
"""
from scenes.single import scene_single
from scenes.mosaic import scene_mosaic
from scenes.typewriting import scene_typewriting
from scenes.parallax import scene_parallax
from scenes.flip_y import scene_flip_y
from scenes.text_highlight import scene_text_highlight

_BUILDERS: dict = {
    "single":      scene_single,
    "mosaic":      scene_mosaic,
    "typewriting": scene_typewriting,
    "parallax":    scene_parallax,
    "flip_y":      scene_flip_y,
    "text_highlight": scene_text_highlight,
}


def build_scene(scene: dict, W: int, H: int, fps: int):
    """
    Constrói o VideoClip para uma cena do project.json.

    Args:
        scene:  dicionário da cena
        W, H:   resolução de destino
        fps:    frames por segundo

    Returns:
        moviepy.VideoClip

    Raises:
        ValueError: se o tipo de cena não estiver registrado
    """
    scene_type = scene.get("type", "single")
    builder = _BUILDERS.get(scene_type)

    if not builder:
        available = list(_BUILDERS)
        raise ValueError(
            f"Tipo de cena desconhecido: '{scene_type}'. "
            f"Disponíveis: {available}"
        )

    return builder(scene, W, H, fps)


__all__ = ["build_scene", "_BUILDERS"]
