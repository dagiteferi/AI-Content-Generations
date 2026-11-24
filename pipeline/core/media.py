import shutil
import subprocess
import wave
from pathlib import Path

from pipeline.errors import FFmpegMissing, StageError


def require_ffmpeg() -> None:
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        raise FFmpegMissing()


def ffmpeg_version() -> str:
    require_ffmpeg()
    output = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, check=True)
    return output.stdout.splitlines()[0]


def run_ffmpeg(arguments: list[str]) -> None:
    require_ffmpeg()
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *arguments]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise StageError(f"ffmpeg failed: {result.stderr.strip()[-1000:]}")


def audio_duration_s(path: Path) -> float:
    try:
        with wave.open(str(path), "rb") as audio:
            return audio.getnframes() / audio.getframerate()
    except (wave.Error, EOFError):
        return _probe_duration_s(path)


def _probe_duration_s(path: Path) -> float:
    require_ffmpeg()
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())
