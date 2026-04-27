"""
transitions/crossfade.py
Transição crossfade entre clipes usando MoviePy.

Compatível com MoviePy 1.x e 2.x (tenta importar o caminho novo primeiro).
"""


def apply_crossfade(clips: list, scenes: list, trans_dur: float) -> list:
    """
    Aplica CrossFadeIn / CrossFadeOut a cada clipe conforme necessário.

    Args:
        clips:      lista de VideoClip (um por cena)
        scenes:     lista de dicts de cena (para verificar transition_out)
        trans_dur:  duração do crossfade em segundos

    Returns:
        lista de VideoClip com efeitos de fade aplicados
    """
    processed = []

    for i, clip in enumerate(clips):
        trans = scenes[i].get("transition_out", "crossfade")
        if trans != "crossfade":
            processed.append(clip)
            continue

        try:
            from moviepy.video.fx.CrossFadeIn import CrossFadeIn
            from moviepy.video.fx.CrossFadeOut import CrossFadeOut

            if i > 0:
                clip = clip.with_effects([CrossFadeIn(trans_dur)])
            if i < len(clips) - 1:
                clip = clip.with_effects([CrossFadeOut(trans_dur)])

        except ImportError:
            # MoviePy 1.x
            if i > 0:
                clip = clip.crossfadein(trans_dur)
            if i < len(clips) - 1:
                clip = clip.crossfadeout(trans_dur)

        processed.append(clip)

    return processed
