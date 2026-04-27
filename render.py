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
import platform
import shutil
import subprocess
import tempfile

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


def detect_hw_encoder() -> tuple[str, list[str]]:
    """
    Detecta encoder de hardware disponível no ffmpeg local.

    Retorna:
      (codec, ffmpeg_params)
    """
    if shutil.which("ffmpeg") is None:
        print("ℹ ffmpeg não encontrado no PATH — usando libx264")
        return "libx264", []

    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        encoders = result.stdout
    except Exception as exc:
        print(f"⚠ Falha ao detectar encoder de hardware: {exc}")
        return "libx264", []

    if "h264_nvenc" in encoders:
        print("🟢 GPU NVIDIA — h264_nvenc")
        return "h264_nvenc", ["-rc", "vbr", "-cq", "23", "-preset", "p4", "-tune", "hq"]

    if platform.system() == "Darwin" and "h264_videotoolbox" in encoders:
        print("🟢 Apple VideoToolbox — h264_videotoolbox")
        return "h264_videotoolbox", ["-allow_sw", "0", "-q:v", "65"]

    print("ℹ Encoder de hardware não encontrado — usando libx264")
    return "libx264", []


def _sanitize_encoder_params(codec: str, params: list[str]) -> list[str]:
    """
    Garante que parâmetros enviados ao ffmpeg sejam compatíveis com o codec.
    Evita passar flags NVENC para VideoToolbox/libx264, causando falha de pipe.
    """
    if not isinstance(params, list):
        return []

    if codec == "h264_nvenc":
        return params

    # Remove pares de opções típicos do NVENC para outros codecs.
    blocked = {"-rc", "-cq", "-tune", "-gpu", "-preset", "-b:v"}
    sanitized: list[str] = []
    i = 0
    while i < len(params):
        token = params[i]
        if token in blocked:
            i += 2
            continue
        sanitized.append(token)
        i += 1

    return sanitized


def _ffmpeg_accepts_encoder(codec: str, params: list[str]) -> tuple[bool, str]:
    """
    Faz smoke test rápido do encoder/params no ffmpeg para evitar falha tardia.
    """
    if shutil.which("ffmpeg") is None:
        return False, "ffmpeg não encontrado"

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp_out = tmp.name

    try:
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=64x64:r=1:d=0.2",
            "-c:v",
            codec,
            *params,
            "-f",
            "mp4",
            tmp_out,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10, check=False)
        if res.returncode == 0:
            return True, ""
        err = (res.stderr or res.stdout or "erro desconhecido").strip()
        return False, err
    except Exception as exc:
        return False, str(exc)
    finally:
        try:
            os.remove(tmp_out)
        except OSError:
            pass


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
    configured_codec = proj.get("encoder")
    configured_params = proj.get("encoder_params")
    encode_threads = int(
        proj.get(
            "encode_threads",
            max(1, (os.cpu_count() or 4) - 1),
        )
    )
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

    if configured_codec:
        codec = configured_codec
        ffmpeg_params = configured_params if isinstance(configured_params, list) else []
        print(f"🎛️  Encoder configurado no JSON: {codec}")
    else:
        codec, ffmpeg_params = detect_hw_encoder()

    ffmpeg_params = _sanitize_encoder_params(codec, ffmpeg_params)

    ok, reason = _ffmpeg_accepts_encoder(codec, ffmpeg_params)
    if not ok:
        print(f"⚠ Encoder '{codec}' inválido com params atuais: {reason}")

        # Tenta auto-detecção antes de cair para software.
        auto_codec, auto_params = detect_hw_encoder()
        auto_params = _sanitize_encoder_params(auto_codec, auto_params)
        auto_ok, auto_reason = _ffmpeg_accepts_encoder(auto_codec, auto_params)

        if auto_ok:
            codec = auto_codec
            ffmpeg_params = auto_params
            print(f"✅ Recuperado com auto-detecção: {codec}")
        else:
            print(f"⚠ Auto-detecção também falhou: {auto_reason}")
            print("ℹ Fallback para libx264 (software)")
            codec = "libx264"
            ffmpeg_params = []

    # ── Escrita do arquivo ────────────────────────────────────────────────────
    print(f"💾  Escrevendo → {output}")
    write_kwargs = {
        "fps": fps,
        "codec": codec,
        "audio_codec": "aac",
        "threads": max(1, encode_threads),
        "logger": "bar",
    }

    if codec == "libx264":
        write_kwargs["preset"] = proj.get("x264_preset", "veryfast")

    if ffmpeg_params:
        write_kwargs["ffmpeg_params"] = ffmpeg_params

    print(f"⚙️  Encode: codec={codec} | threads={write_kwargs['threads']}")
    print("ℹ Composição de frames (efeitos Python/PIL) no MoviePy tende a ser majoritariamente single-thread.")

    final.write_videofile(output, **write_kwargs)
    print(f"\n✅  Concluído! → {output}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python render.py project.json")
        sys.exit(1)
    render(sys.argv[1])