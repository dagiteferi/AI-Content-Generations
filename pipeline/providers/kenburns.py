"""Slow pan and zoom over a still: the fallback when a generated clip is missing."""

from pathlib import Path

from pipeline.core.media import run_ffmpeg

FPS = 24
OUTPUT_SIZE = 1024
ZOOM = 1.12
PAN_ZOOM = 1.08
CENTRE_X = "iw/2-(iw/zoom/2)"
CENTRE_Y = "ih/2-(ih/zoom/2)"


def motion_expressions(camera: str, frames: int, still: bool = False) -> tuple[str, str, str]:
    """Return zoompan (zoom, x, y) expressions that follow the storyboard's camera note."""
    camera = camera.lower()
    progress = f"on/{frames}"

    if still or "locked" in camera or "static" in camera:
        return "1", CENTRE_X, CENTRE_Y
    if "pull" in camera or "out" in camera:
        return f"{ZOOM}-({ZOOM}-1)*{progress}", CENTRE_X, CENTRE_Y
    if "left" in camera:
        return str(PAN_ZOOM), f"(iw-iw/zoom)*(1-{progress})", CENTRE_Y
    if "right" in camera:
        return str(PAN_ZOOM), f"(iw-iw/zoom)*{progress}", CENTRE_Y
    if "down" in camera:
        return str(PAN_ZOOM), CENTRE_X, f"(ih-ih/zoom)*{progress}"
    if "up" in camera:
        return str(PAN_ZOOM), CENTRE_X, f"(ih-ih/zoom)*(1-{progress})"
    return f"1+({ZOOM}-1)*{progress}", CENTRE_X, CENTRE_Y


def kenburns_filter(camera: str, frames: int, still: bool = False) -> str:
    zoom, x, y = motion_expressions(camera, frames, still)
    return (
        f"scale={OUTPUT_SIZE * 2}:{OUTPUT_SIZE * 2}:force_original_aspect_ratio=increase,"
        f"crop={OUTPUT_SIZE * 2}:{OUTPUT_SIZE * 2},"
        f"zoompan=z='{zoom}':x='{x}':y='{y}':d={frames}:s={OUTPUT_SIZE}x{OUTPUT_SIZE}:fps={FPS},"
        "format=yuv420p"
    )


def render_kenburns(image: Path, output: Path, camera: str, duration_s: float, still: bool = False) -> None:
    frames = max(1, round(duration_s * FPS))
    run_ffmpeg(
        [
            "-i", str(image),
            "-vf", kenburns_filter(camera, frames, still),
            "-frames:v", str(frames),
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-r", str(FPS),
            str(output),
        ]
    )
