"""Final edit: shots cut to the narration, ducked score, burned subtitles, end card, both ratios.

Two steps, each cached by a hash of its inputs:
1. `mix.wav`: narration + score (chosen ACE-Step track, else placeholder), ducked,
   then a two-pass loudness normalisation to -14 LUFS / -1 dBTP.
2. One MP4 per aspect ratio: every shot centre-cropped from its square clip, held to
   its narration slot, an end card, subtitles burned in from an ASS file sized for that frame.
"""

import json
import textwrap
from dataclasses import dataclass
from pathlib import Path

from pipeline.context import StageContext
from pipeline.core.cache import atomic_output, cache_key, file_digest
from pipeline.core.media import audio_duration_s, measure_loudness, require_ffmpeg, run_ffmpeg
from pipeline.core.retry import call_with_retry
from pipeline.core.runlog import Call
from pipeline.errors import StageError
from pipeline.models import Storyboard
from pipeline.stages import music, shots
from pipeline.stages.narration import narration_path
from pipeline.stages.radio import (
    DUCKING,
    FRAME_RATE,
    SAMPLE_RATE,
    Cue,
    Slot,
    placeholder_music,
    voice_graph,
    plan_timeline,
    subtitle_cues,
    to_srt,
)

STAGE = "final"
LOUDNESS_TARGET = {"I": -14.0, "TP": -1.0, "LRA": 11.0}
VOICE_LUFS = -16.0
MUSIC_LUFS = -26.0
MUSIC_FADE_S = 2.0
CLIP_HEAD_TRIM_S = 0.25
MAX_STRETCH = 1.5
SHOT_FADE_S = 0.5
END_CARD_WIDTH = 28


@dataclass(frozen=True)
class Ratio:
    name: str
    width: int
    height: int
    font_size: int
    margin_v: int

    @property
    def aspect(self) -> float:
        return self.width / self.height


# Vertical subtitles sit above the bottom ~20% where TikTok/Reels/Shorts draw their buttons.
RATIOS = (
    Ratio("9x16", 1080, 1920, font_size=46, margin_v=420),
    Ratio("16x9", 1920, 1080, font_size=50, margin_v=70),
)


@dataclass(frozen=True)
class ClipInput:
    path: Path
    duration_s: float
    generated: bool  # a Wan clip (trim its weak first frames) rather than a local fallback


# ---------------------------------------------------------------- audio


def place_cues(storyboard: Storyboard, slots: list[Slot]) -> list[tuple[float, float]]:
    """Map each music cue from planned time to the actual (narration-stretched) timeline."""
    planned = sum(shot.duration_s for shot in storyboard.shots)
    actual = slots[-1].end_s
    scale = actual / planned
    return [(cue.start_s * scale, cue.end_s * scale) for cue in storyboard.music.cues]


def music_graph(tracks: list[Path] | None, placements: list[tuple[float, float]], total_s: float, first_input: int) -> str:
    """Filter graph producing [music]: chosen tracks at their cue times, or placeholder tones."""
    if not tracks:
        return placeholder_music(total_s)

    parts = []
    for index, (track_input, (start, end)) in enumerate(zip(range(first_input, first_input + len(tracks)), placements)):
        length = end - start
        fade_at = max(0.0, length - MUSIC_FADE_S)
        delay_ms = round(start * 1000)
        parts.append(
            f"[{track_input}:a]aresample={SAMPLE_RATE},aformat=sample_fmts=fltp:channel_layouts=mono,"
            f"atrim=duration={length:.3f},loudnorm=I={MUSIC_LUFS}:TP=-2,aresample={SAMPLE_RATE},"
            f"afade=t=in:d={MUSIC_FADE_S},afade=t=out:st={fade_at:.3f}:d={MUSIC_FADE_S},"
            f"adelay={delay_ms}:all=1,apad=whole_dur={total_s:.3f}[cue{index}]"
        )
    labels = "".join(f"[cue{i}]" for i in range(len(tracks)))
    parts.append(f"{labels}amix=inputs={len(tracks)}:normalize=0,atrim=duration={total_s:.3f}[music]")
    return ";".join(parts)


def premix_command(
    narration_files: list[Path | None],
    slots: list[Slot],
    end_card_s: float,
    tracks: list[Path] | None,
    placements: list[tuple[float, float]],
    output: Path,
) -> list[str]:
    total_s = slots[-1].end_s + end_card_s
    inputs, voice = voice_graph(narration_files, slots, end_card_s)
    graph = [
        *voice,
        f"[voicecat]loudnorm=I={VOICE_LUFS}:TP=-2,aresample={SAMPLE_RATE},asplit=2[voice][sidechain]",
        music_graph(tracks, placements, total_s, first_input=len(inputs) // 2),
        f"[music][sidechain]sidechaincompress={DUCKING}[ducked]",
        "[voice][ducked]amix=inputs=2:duration=first:normalize=0[mix]",
    ]
    inputs += [arg for path in tracks or [] for arg in ("-i", str(path))]
    return [*inputs, "-filter_complex", ";".join(graph), "-map", "[mix]", "-c:a", "pcm_s16le", str(output)]


def loudnorm_second_pass(measured: dict, source: Path, output: Path) -> list[str]:
    target = LOUDNESS_TARGET
    loudnorm = (
        f"loudnorm=I={target['I']}:TP={target['TP']}:LRA={target['LRA']}"
        f":measured_I={measured['input_i']}:measured_TP={measured['input_tp']}"
        f":measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}"
        f":offset={measured['target_offset']}:linear=true"
    )
    return ["-i", str(source), "-af", f"{loudnorm},aresample={SAMPLE_RATE}", "-ac", "2", "-c:a", "pcm_s16le", str(output)]


# ---------------------------------------------------------------- picture


def crop_scale(ratio: Ratio) -> str:
    """Centre-crop any source to the ratio, then scale to the frame (subjects are composed centred)."""
    a = f"{ratio.aspect:.6f}"
    return (
        f"crop=w='min(iw,ih*{a})':h='min(ih,iw/{a})',"
        f"scale={ratio.width}:{ratio.height}:flags=lanczos,setsar=1"
    )


def shot_filter(index: int, clip: ClipInput, slot: Slot, ratio: Ratio, last: bool) -> str:
    """Fit one clip to its slot: trim weak head, slow it a little if short, then hold the last frame."""
    head = CLIP_HEAD_TRIM_S if clip.generated and clip.duration_s > 2 * CLIP_HEAD_TRIM_S + 1 else 0.0
    usable = clip.duration_s - head
    stretch = min(MAX_STRETCH, max(1.0, slot.length_s / usable))
    hold = max(0.0, slot.length_s - usable * stretch)
    chain = [
        f"[{index}:v]trim=start={head:.3f}",
        f"setpts=(PTS-STARTPTS)*{stretch:.4f}",
        f"fps={FRAME_RATE}",
        crop_scale(ratio),
        f"tpad=stop_mode=clone:stop_duration={hold + 0.1:.3f}",
        f"trim=duration={slot.length_s:.3f}",
        "setpts=PTS-STARTPTS",
    ]
    if index == 0:
        chain.append(f"fade=t=in:d={SHOT_FADE_S}")
    if last:
        chain.append(f"fade=t=out:st={slot.length_s - SHOT_FADE_S:.3f}:d={SHOT_FADE_S}")
    return ",".join(chain) + f",format=yuv420p[v{index}]"


def ass_time(seconds: float) -> str:
    centis = round(seconds * 100)
    hours, centis = divmod(centis, 360_000)
    minutes, centis = divmod(centis, 6000)
    secs, centis = divmod(centis, 100)
    return f"{hours}:{minutes:02}:{secs:02}.{centis:02}"


def ass_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")").replace("\n", "\\N")


def to_ass(cues: list[Cue], ratio: Ratio, end_card: str, end_start_s: float, end_s: float) -> str:
    """Subtitles plus the end card text, in pixels of this frame, so nothing is rescaled by libass."""
    card = ass_escape("\n".join(textwrap.wrap(end_card, END_CARD_WIDTH)))
    style = "Fontname,Fontsize,PrimaryColour,OutlineColour,BackColour,Bold,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV"
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {ratio.width}",
        f"PlayResY: {ratio.height}",
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        f"Format: Name,{style}",
        f"Style: Sub,DejaVu Sans,{ratio.font_size},&H00FFFFFF,&H00000000,&H80000000,0,1,3,1,2,60,60,{ratio.margin_v}",
        f"Style: Card,DejaVu Sans,{round(ratio.font_size * 1.3)},&H00FFFFFF,&H00000000,&H00000000,1,1,0,0,5,80,80,0",
        "",
        "[Events]",
        "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text",
    ]
    lines += [f"Dialogue: 0,{ass_time(c.start_s)},{ass_time(c.end_s)},Sub,,0,0,0,,{ass_escape(c.text)}" for c in cues]
    lines.append(f"Dialogue: 0,{ass_time(end_start_s)},{ass_time(end_s)},Card,,0,0,0,,{{\\fad(400,0)}}{card}")
    return "\n".join(lines) + "\n"


def filter_path(path: Path) -> str:
    """Escape a path for use inside an FFmpeg filter argument."""
    return str(path).replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def picture_command(
    clips: list[ClipInput], slots: list[Slot], ratio: Ratio, end_card_s: float, subtitles: Path, audio: Path, output: Path
) -> list[str]:
    total_s = slots[-1].end_s + end_card_s
    end_input = len(clips)
    audio_input = end_input + 1
    graph = [shot_filter(i, clip, slot, ratio, last=i == len(clips) - 1) for i, (clip, slot) in enumerate(zip(clips, slots))]
    graph.append(f"[{end_input}:v]format=yuv420p[vend]")
    labels = "".join(f"[v{i}]" for i in range(len(clips))) + "[vend]"
    graph.append(f"{labels}concat=n={len(clips) + 1}:v=1:a=0,subtitles=filename='{filter_path(subtitles)}'[video]")

    inputs = [arg for clip in clips for arg in ("-i", str(clip.path))]
    return [
        *inputs,
        "-f", "lavfi", "-i", f"color=c=black:s={ratio.width}x{ratio.height}:r={FRAME_RATE}:d={end_card_s:.3f}",
        "-i", str(audio),
        "-filter_complex", ";".join(graph),
        "-map", "[video]", "-map", f"{audio_input}:a",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(FRAME_RATE),
        "-c:a", "aac", "-b:a", "192k",
        "-t", f"{total_s:.3f}",
        "-movflags", "+faststart",
        str(output),
    ]


# ---------------------------------------------------------------- stage


def _manifest_key(path: Path) -> str | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8")).get("key")


def _collect_inputs(ctx: StageContext) -> tuple[dict[str, Path | None], dict[str, Path], list[Path] | None]:
    storyboard = ctx.storyboard
    outputs_dir = ctx.settings.outputs_dir
    narration = {s.id: narration_path(outputs_dir, s, storyboard.voice) for s in storyboard.shots}
    clips = {s.id: shots.resolve_clip(outputs_dir, s, storyboard) for s in storyboard.shots}

    missing_voice = [k for k, p in narration.items() if p is not None and not p.exists()]
    missing_clip = [k for k, p in clips.items() if p is None]
    problems = []
    if missing_voice:
        problems.append(f"narration for {', '.join(missing_voice)} (heritage run --stage narration)")
    if missing_clip:
        problems.append(f"a clip or fallback for {', '.join(missing_clip)} (heritage run --stage shots)")
    if problems:
        raise StageError("Assembly needs " + " and ".join(problems))

    tracks = [music.chosen_track(outputs_dir, storyboard.music, cue) for cue in storyboard.music.cues]
    chosen = tracks if tracks and all(tracks) else None
    return narration, clips, chosen  # type: ignore[return-value]


def run(ctx: StageContext) -> None:
    storyboard = ctx.storyboard
    try:
        narration, clips, tracks = _collect_inputs(ctx)
    except StageError:
        if ctx.dry_run:
            ctx.status("film", "would generate", note="after narration and shots")
            return
        raise

    if tracks is None:
        ctx.console.print("  [yellow]no chosen score yet:[/] using placeholder music (set music.chosen_seed)")

    out_dir = ctx.stage_dir(STAGE)
    end_card = storyboard.end_card
    voice_digests = [file_digest(p) if p else "silent" for p in narration.values()]
    mix_key = cache_key(
        {
            "stage": f"{STAGE}-mix",
            "narration": voice_digests,
            "planned": [s.duration_s for s in storyboard.shots],
            "cues": [[c.start_s, c.end_s] for c in storyboard.music.cues],
            "music": [t.name for t in tracks] if tracks else "placeholder",
            "end_card_s": end_card.duration_s,
            "mix": [DUCKING, VOICE_LUFS, MUSIC_LUFS, LOUDNESS_TARGET],
        }
    )
    mix = out_dir / f"mix.{mix_key}.wav"
    film_keys = {
        ratio.name: cache_key(
            {
                "stage": f"{STAGE}-{ratio.name}",
                "mix": mix_key,
                "clips": [clips[s.id].name for s in storyboard.shots],
                "subtitles": [s.narration.subtitle if s.narration else "" for s in storyboard.shots],
                "end_card": end_card.text,
                "ratio": [ratio.width, ratio.height, ratio.font_size, ratio.margin_v],
                "edit": [CLIP_HEAD_TRIM_S, MAX_STRETCH, SHOT_FADE_S],
            }
        )
        for ratio in RATIOS
    }

    def film_path(ratio: Ratio) -> Path:
        return out_dir / f"film_{ratio.name}.mp4"

    def manifest_path(ratio: Ratio) -> Path:
        return out_dir / f"film_{ratio.name}.json"

    pending = [r for r in RATIOS if ctx.force or not film_path(r).exists() or _manifest_key(manifest_path(r)) != film_keys[r.name]]
    for ratio in RATIOS:
        if ratio not in pending:
            ctx.log.record(Call(stage="assemble", provider="local", model="ffmpeg", params={"ratio": ratio.name}),
                           status="ok", cache="hit", attempt=0, output=film_path(ratio))
            ctx.status(ratio.name, "cached", film_path(ratio))
    if not pending:
        return
    if ctx.dry_run:
        for ratio in pending:
            ctx.status(ratio.name, "would generate", film_path(ratio))
        return

    require_ffmpeg()
    narration_s = {k: audio_duration_s(p) for k, p in narration.items() if p is not None}
    slots = plan_timeline(storyboard, narration_s)
    total_s = slots[-1].end_s + end_card.duration_s

    if mix.exists() and not ctx.force:
        ctx.status("mix", "cached", mix)
    else:
        _render_mix(ctx, list(narration.values()), slots, tracks, mix)

    cues = subtitle_cues(slots)
    (out_dir / "film.srt").write_text(to_srt(cues), encoding="utf-8")
    clip_inputs = [
        ClipInput(
            clips[s.id],
            audio_duration_s(clips[s.id]),
            generated=clips[s.id] == shots.clip_path(ctx.settings.outputs_dir, s, storyboard),
        )
        for s in storyboard.shots
    ]

    for ratio in pending:
        subtitles = out_dir / f"film_{ratio.name}.ass"
        subtitles.write_text(to_ass(cues, ratio, end_card.text, slots[-1].end_s, total_s), encoding="utf-8")
        output = film_path(ratio)
        call = Call(stage="assemble", provider="local", model="ffmpeg",
                    params={"ratio": ratio.name, "size": f"{ratio.width}x{ratio.height}"})
        with atomic_output(output) as temporary:
            command = picture_command(clip_inputs, slots, ratio, end_card.duration_s, subtitles, mix, temporary)
            call_with_retry(lambda: run_ffmpeg(command), call=call, log=ctx.log, max_attempts=1, output=output)
        summary = {
            "key": film_keys[ratio.name],
            "total_s": round(total_s, 3),
            "mix": mix.name,
            "music": [t.name for t in tracks] if tracks else "placeholder",
            "clips": {s.id: c.path.name for s, c in zip(storyboard.shots, clip_inputs)},
        }
        manifest_path(ratio).write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        ctx.status(ratio.name, "generated", output, f"{total_s:.1f}s")


def _render_mix(ctx: StageContext, narration: list[Path | None], slots: list[Slot], tracks: list[Path] | None, mix: Path) -> None:
    storyboard = ctx.storyboard
    premix = mix.with_name(f".premix.{mix.name}")
    placements = place_cues(storyboard, slots)
    call = Call(stage="assemble", provider="local", model="ffmpeg",
                params={"step": "mix", "ducking": DUCKING, "target": LOUDNESS_TARGET})

    def render() -> dict:
        run_ffmpeg(premix_command(narration, slots, storyboard.end_card.duration_s, tracks, placements, premix))
        measured = measure_loudness(premix, LOUDNESS_TARGET)
        with atomic_output(mix) as temporary:
            run_ffmpeg(loudnorm_second_pass(measured, premix, temporary))
        return measured

    try:
        measured = call_with_retry(render, call=call, log=ctx.log, max_attempts=1, output=mix)
    finally:
        premix.unlink(missing_ok=True)
    ctx.status("mix", "generated", mix, f"premix {measured['input_i']} LUFS -> {LOUDNESS_TARGET['I']}")
