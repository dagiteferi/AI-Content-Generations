import json
import re
import subprocess
import wave
from functools import cache
from pathlib import Path

import imageio_ffmpeg

from pipeline.errors import FFmpegMissing, StageError


@cache
def ffmpeg_exe() -> str:
    # The binary ships with the imageio-ffmpeg package, so `uv sync` is enough.
    # Set IMAGEIO_FFMPEG_EXE to use a different FFmpeg.
    try:
        return imageio_ffmpeg.get_ffmpeg_exe()
    except RuntimeError as error:
        raise FFmpegMissing() from error


def require_ffmpeg() -> None:
    ffmpeg_exe()


def ffmpeg_version() -> str:
    output = subprocess.run([ffmpeg_exe(), "-version"], capture_output=True, text=True, check=True)
    return output.stdout.splitlines()[0]


def run_ffmpeg(arguments: list[str]) -> None:
    command = [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", *arguments]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise StageError(f"ffmpeg failed: {result.stderr.strip()[-1000:]}")


def audio_duration_s(path: Path) -> float:
    try:
        with wave.open(str(path), "rb") as audio:
            return audio.getnframes() / audio.getframerate()
    except (wave.Error, EOFError):
        return media_duration_s(path)


def media_duration_s(path: Path) -> float:
    """Duration of any audio or video file, read from FFmpeg's header line (no ffprobe needed)."""
    result = subprocess.run([ffmpeg_exe(), "-hide_banner", "-i", str(path)], capture_output=True, text=True)
    match = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", result.stderr)
    if match is None:
        raise StageError(f"Could not read the duration of {path.name}")
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def measure_loudness(path: Path, target: dict[str, float]) -> dict[str, str]:
    """First loudnorm pass: measure integrated loudness, true peak and range of `path`."""
    loudnorm = f"loudnorm=I={target['I']}:TP={target['TP']}:LRA={target['LRA']}:print_format=json"
    result = subprocess.run(
        [ffmpeg_exe(), "-hide_banner", "-nostats", "-i", str(path), "-af", loudnorm, "-f", "null", "-"],
        capture_output=True,
        text=True,
    )
    match = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", result.stderr)
    if result.returncode != 0 or match is None:
        raise StageError(f"loudness measurement failed: {result.stderr.strip()[-500:]}")
    return json.loads(match.group(0))
