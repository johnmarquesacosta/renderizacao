#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║  render.py — Motor de Renderização de Vídeo                 ║
║  Lê project.json e gera o vídeo final com efeitos dinâmicos ║
║                                                             ║
║  Uso: python render.py project.json                         ║
╚══════════════════════════════════════════════════════════════╝

Arquitetura modular:
  utils/        → carregamento de imagem, fontes, helpers
  effects/      → ken_burns, overlays (grain, vignette, desaturate)
  scenes/       → single, mosaic, typewriting, parallax
  transitions/  → crossfade
"""

import json
import os
import sys
import importlib

# ── MoviePy: suporta 1.x e 2.x ───────────────────────────────────────────────
try:
    _moviepy = importlib.import_module("moviepy.editor")
except ModuleNotFoundError:
    _moviepy = importlib.import_module("moviepy")

concatenate_videoclips = _moviepy.concatenate_videoclips
AudioFileClip = _moviepy.AudioFileClip

# ── Módulos do projeto ────────────────────────────────────────────────────────
from scenes import build_scene
from transitions.crossfade import apply_crossfade


# ══════════════════════════════════════════════════════════════════════════════
# MONTAGEM FINAL
# ══════════════════════════════════════════════════════════════════════════════

def assemble(clips: list, scenes: list, default_trans: str, trans_dur: float):
    """
    Concatena clipes com as transições definidas por cena.

    Args:
        clips:        lista de VideoClip
        scenes:       lista de dicts (para ler transition_out por cena)
        default_trans: tipo de transição padrão
        trans_dur:    duração da transição em segundos

    Returns:
        VideoClip concatenado final
    """
    if len(clips) == 1:
        return clips[0]

    # Aplica transições (atualmente: crossfade)
    processed = apply_crossfade(clips, scenes, trans_dur)

    return concatenate_videoclips(
        processed,
        padding=-trans_dur,
        method="compose",
    )


# ══════════════════════════════════════════════════════════════════════════════
# PONTO DE ENTRADA
# ══════════════════════════════════════════════════════════════════════════════

def render(project_path: str) -> None:
    with open(project_path, encoding="utf-8") as f:
        proj = json.load(f)

    fps      = proj.get("fps", 30)
    W, H     = proj.get("resolution", [1920, 1080])
    output   = proj.get("output", "output.mp4")
    scenes   = proj["scenes"]
    tc       = proj.get("transitions", {})
    def_trans = tc.get("default", "crossfade")
    trans_dur = float(tc.get("duration", 0.5))

    dur_est = sum(s.get("duration", 4) for s in scenes)
    print(f"\n🎬  {proj.get('title', 'Vídeo')}")
    print(f"    {len(scenes)} cenas | {W}×{H} @ {fps}fps | ~{dur_est / 60:.1f} min estimado\n")

    # ── Renderiza cada cena ───────────────────────────────────────────────────
    clips = []
    for i, scene in enumerate(scenes):
        label = (
            f"  [{i + 1:3d}/{len(scenes)}] "
            f"type={scene['type']:<12s} "
            f"dur={scene.get('duration', '?')}s"
        )
        print(label, end="\r", flush=True)
        clips.append(build_scene(scene, W, H, fps))

    # ── Monta com transições ──────────────────────────────────────────────────
    print(f"\n\n🔗  Montando {len(clips)} cenas ({def_trans}, {trans_dur}s)...")
    final = assemble(clips, scenes, def_trans, trans_dur)

    # ── Áudio ─────────────────────────────────────────────────────────────────
    audio_path = proj.get("audio")
    if audio_path and os.path.exists(audio_path):
        print(f"🔊  Áudio: {audio_path}")
        audio = AudioFileClip(audio_path)
        min_dur = min(audio.duration, final.duration)
        audio = audio.subclipped(0, min_dur)
        final = final.subclipped(0, min_dur).with_audio(audio)
    elif audio_path:
        print(f"⚠   Áudio não encontrado: {audio_path}")

    # ── Escrita do arquivo ────────────────────────────────────────────────────
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
    print(f"\n✅  Concluído! → {output}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python render.py project.json")
        sys.exit(1)
    render(sys.argv[1])