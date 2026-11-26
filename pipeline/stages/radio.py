"""Radio cut: the narration over placeholder music on a black screen."""

import json
import textwrap
from dataclasses import asdict, dataclass
from pathlib import Path

from rich.console import Console
from rich.table import Table

from pipeline.context import StageContext
from pipeline.core.cache import atomic_output, cache_key, file_digest
from pipeline.core.media import audio_duration_s, require_ffmpeg, run_ffmpeg
from pipeline.core.retry import call_with_retry
from pipeline.core.runlog import Call
from pipeline.errors import StageError
from pipeline.models import Storyboard
from pipeline.stages.narration import narration_path

STAGE = "radio_cut"
SAMPLE_RATE = 48_000
FRAME_SIZE = (1080, 1920)
FRAME_RATE = 24
NARRATION_TAIL_S = 0.4
SUBTITLE_WIDTH = 40
SUBTITLE_LINES = 2
DUCKING = "threshold=0.02:ratio=6:attack=300:release=1500"
LOUDNESS = "I=-14:TP=-1:LRA=11"
PLACEHOLDER_TONES_HZ = (110.0, 164.81, 220.0)


@dataclass(frozen=True)
class Slot:
    shot_id: str
    start_s: float
    length_s: float
    planned_s: float
    narration_s: float
    subtitle: str

    @property
    def end_s(self) -> float:
        return self.start_s + self.length_s

    @property
    def overrun_s(self) -> float:
        return max(0.0, self.length_s - self.planned_s)


@dataclass(frozen=True)
class Cue:
    start_s: float
    end_s: float
    text: str


def plan_timeline(storyboard: Storyboard, narration_s: dict[str, float]) -> list[Slot]:
    slots: list[Slot] = []
    cursor = 0.0
    for shot in storyboard.shots:
        spoken = narration_s.get(shot.id, 0.0)
        length = max(shot.duration_s, spoken + NARRATION_TAIL_S) if spoken else shot.duration_s
        subtitle = shot.narration.subtitle if shot.narration else ""
        slots.append(Slot(shot.id, cursor, length, shot.duration_s, spoken, subtitle))
        cursor += length
    return slots


def subtitle_chunks(text: str) -> list[str]:
    lines = textwrap.wrap(text, SUBTITLE_WIDTH)
    return ["\n".join(lines[i : i + SUBTITLE_LINES]) for i in range(0, len(lines), SUBTITLE_LINES)]


def subtitle_cues(slots: list[Slot]) -> list[Cue]:
    cues: list[Cue] = []
    for slot in slots:
        if not slot.subtitle:
            continue
        chunks = subtitle_chunks(slot.subtitle)
        total_chars = sum(len(chunk) for chunk in chunks)
        start = slot.start_s
        for chunk in chunks:
            length = slot.narration_s * len(chunk) / total_chars
            cues.append(Cue(start, start + length, chunk))
            start += length
    return cues


def srt_timestamp(seconds: float) -> str:
    millis = round(seconds * 1000)
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def to_srt(cues: list[Cue]) -> str:
    blocks = [
        f"{index}\n{srt_timestamp(cue.start_s)} --> {srt_timestamp(cue.end_s)}\n{cue.text}\n"
        for index, cue in enumerate(cues, start=1)
    ]
    return "\n".join(blocks)


def placeholder_music(duration_s: float) -> str:
    tones = [
        f"sine=frequency={hz}:sample_rate={SAMPLE_RATE}:duration={duration_s:.3f}[tone{i}]"
        for i, hz in enumerate(PLACEHOLDER_TONES_HZ)
    ]
    labels = "".join(f"[tone{i}]" for i in range(len(PLACEHOLDER_TONES_HZ)))
    fade_out_at = max(0.0, duration_s - 3)
    mix = (
        f"{labels}amix=inputs={len(PLACEHOLDER_TONES_HZ)},lowpass=f=900,volume=0.25,"
        f"afade=t=in:d=2,afade=t=out:st={fade_out_at:.3f}:d=3[music]"
    )
    return ";".join([*tones, mix])


def voice_graph(files: list[Path | None], slots: list[Slot], end_card_s: float) -> tuple[list[str], list[str]]:
    """Inputs and filter lines for the voice track: each line padded to its slot, silence for silent shots."""
    inputs: list[str] = []
    parts: list[str] = []
    for i, (path, slot) in enumerate(zip(files, slots)):
        if path is None:
            parts.append(f"anullsrc=r={SAMPLE_RATE}:cl=mono,atrim=duration={slot.length_s:.3f}[n{i}]")
            continue
        parts.append(
            f"[{len(inputs) // 2}:a]aresample={SAMPLE_RATE},aformat=sample_fmts=fltp:channel_layouts=mono,"
            f"apad=whole_dur={slot.length_s:.3f}[n{i}]"
        )
        inputs += ["-i", str(path)]
    parts.append(f"anullsrc=r={SAMPLE_RATE}:cl=mono,atrim=duration={end_card_s:.3f}[tail]")
    labels = "".join(f"[n{i}]" for i in range(len(slots))) + "[tail]"
    parts.append(f"{labels}concat=n={len(slots) + 1}:v=0:a=1[voicecat]")
    return inputs, parts


def build_command(
    narration_files: list[Path | None],
    slots: list[Slot],
    end_card_s: float,
    subtitles: Path,
    output: Path,
) -> list[str]:
    total_s = slots[-1].end_s + end_card_s
    width, height = FRAME_SIZE
    inputs, voice = voice_graph(narration_files, slots, end_card_s)
    video_input = len(inputs) // 2
    subtitle_input = video_input + 1

    graph = [
        *voice,
        "[voicecat]asplit=2[voice][sidechain]",
        placeholder_music(total_s),
        f"[music][sidechain]sidechaincompress={DUCKING}[ducked]",
        f"[voice][ducked]amix=inputs=2:duration=first:normalize=0,"
        f"loudnorm={LOUDNESS},aresample={SAMPLE_RATE}[mix]",
    ]

    return [
        *inputs,
        "-f", "lavfi", "-i", f"color=c=black:s={width}x{height}:r={FRAME_RATE}:d={total_s:.3f}",
        "-i", str(subtitles),
        "-filter_complex", ";".join(graph),
        "-map", f"{video_input}:v", "-map", "[mix]", "-map", f"{subtitle_input}:s",
        "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-c:s", "mov_text", "-metadata:s:s:0", "language=eng",
        "-movflags", "+faststart",
        str(output),
    ]


def print_timing(console: Console, slots: list[Slot], end_card_s: float) -> None:
    table = Table(title="Narration timing", show_edge=False)
    for column in ("Shot", "Planned", "Narration", "Slot", "Note"):
        table.add_column(column, justify="left" if column in ("Shot", "Note") else "right")
    for slot in slots:
        note = f"[yellow]+{slot.overrun_s:.1f}s over plan[/]" if slot.overrun_s else ""
        table.add_row(
            slot.shot_id,
            f"{slot.planned_s:.1f}s",
            f"{slot.narration_s:.1f}s",
            f"{slot.length_s:.1f}s",
            note,
        )
    total = slots[-1].end_s + end_card_s
    table.add_row("total", "", "", f"{total:.1f}s", "incl. end card")
    console.print(table)


def _manifest_key(manifest: Path) -> str | None:
    if not manifest.exists():
        return None
    return json.loads(manifest.read_text(encoding="utf-8")).get("key")


def run(ctx: StageContext) -> None:
    storyboard = ctx.storyboard
    voice = storyboard.voice
    files = {shot.id: narration_path(ctx.settings.outputs_dir, shot, voice) for shot in storyboard.shots}

    missing = [shot_id for shot_id, path in files.items() if path is not None and not path.exists()]
    if missing:
        if ctx.dry_run:
            ctx.status("radio", "would generate", note="after narration")
            return
        raise StageError(
            f"Narration missing for {', '.join(missing)}. Run: heritage run --stage narration"
        )

    narration_s = {shot_id: audio_duration_s(path) for shot_id, path in files.items() if path is not None}
    slots = plan_timeline(storyboard, narration_s)
    end_card_s = storyboard.end_card.duration_s
    print_timing(ctx.console, slots, end_card_s)

    out_dir = ctx.stage_dir(STAGE)
    video = out_dir / "radio.mp4"
    subtitles = out_dir / "radio.srt"
    manifest = out_dir / "radio.json"
    key = cache_key(
        {
            "stage": STAGE,
            "narration": [file_digest(path) if path else "silent" for path in files.values()],
            "subtitles": [shot.narration.subtitle if shot.narration else "" for shot in storyboard.shots],
            "planned": [shot.duration_s for shot in storyboard.shots],
            "end_card_s": end_card_s,
            "mix": [DUCKING, LOUDNESS, PLACEHOLDER_TONES_HZ],
        }
    )

    call = Call(stage=STAGE, provider="local", model="ffmpeg", params={"ducking": DUCKING, "loudness": LOUDNESS})

    if video.exists() and _manifest_key(manifest) == key and not ctx.force:
        ctx.log.record(call, status="ok", cache="hit", attempt=0, output=video)
        ctx.status("radio", "cached", video)
        return
    if ctx.dry_run:
        ctx.status("radio", "would generate", video)
        return

    require_ffmpeg()
    subtitles.write_text(to_srt(subtitle_cues(slots)), encoding="utf-8")

    with atomic_output(video) as temporary:
        command = build_command(list(files.values()), slots, end_card_s, subtitles, temporary)
        call_with_retry(lambda: run_ffmpeg(command), call=call, log=ctx.log, max_attempts=1, output=video)

    total_s = slots[-1].end_s + end_card_s
    summary = {"key": key, "total_s": round(total_s, 3), "slots": [asdict(slot) for slot in slots]}
    manifest.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    ctx.status("radio", "generated", video, f"{total_s:.1f}s")
