"""Moving shots: Wan 2.2 clips made on Kaggle, with a local Ken Burns fallback."""

from pathlib import Path

from pipeline.context import StageContext
from pipeline.core.cache import atomic_output, cache_key
from pipeline.core.retry import call_with_retry
from pipeline.core.runlog import Call
from pipeline.errors import StageError
from pipeline.models import Shot, Storyboard
from pipeline.providers.kenburns import render_kenburns
from pipeline.stages.keyframes import keyframe_path

STAGE = "shots"
FPS = 24
WAN_STEPS = 40
WAN_GUIDANCE = 5.0
SQUARE_SIZE = {"480p": 640, "720p": 960}


def clip_path(outputs_dir: Path, shot: Shot, storyboard: Storyboard) -> Path:
    motion = shot.motion
    key = cache_key(
        {
            "stage": STAGE,
            "model": motion.model,
            "keyframe": keyframe_path(outputs_dir, shot, storyboard).name,
            "prompt": motion.prompt,
            "seed": motion.seed,
            "size": SQUARE_SIZE[motion.resolution],
            "frames": motion.frames,
            "steps": WAN_STEPS,
            "guidance": WAN_GUIDANCE,
        }
    )
    return outputs_dir / STAGE / f"{shot.id}.{key}.mp4"


def fallback_path(outputs_dir: Path, shot: Shot, storyboard: Storyboard) -> Path:
    key = cache_key(
        {
            "stage": f"{STAGE}-{shot.fallback}",
            "keyframe": keyframe_path(outputs_dir, shot, storyboard).name,
            "camera": shot.camera,
            "duration_s": shot.duration_s,
        }
    )
    return outputs_dir / STAGE / f"{shot.id}.{key}.{shot.fallback}.mp4"


def resolve_clip(outputs_dir: Path, shot: Shot, storyboard: Storyboard) -> Path | None:
    for path in (clip_path(outputs_dir, shot, storyboard), fallback_path(outputs_dir, shot, storyboard)):
        if path.exists():
            return path
    return None


def run(ctx: StageContext) -> None:
    storyboard = ctx.storyboard
    outputs_dir = ctx.settings.outputs_dir
    waiting: list[str] = []

    for shot in ctx.selected_shots():
        keyframe = keyframe_path(outputs_dir, shot, storyboard)
        if not keyframe.exists():
            if ctx.dry_run:
                ctx.status(shot.id, "would generate", note="after keyframes")
                continue
            raise StageError(f"Keyframe missing for {shot.id}. Run: heritage run --stage keyframes")

        clip = clip_path(outputs_dir, shot, storyboard)
        gpu_call = Call(stage=STAGE, provider="kaggle", model=shot.motion.model, shot=shot.id, seed=shot.motion.seed)
        if clip.exists():
            ctx.log.record(gpu_call, status="ok", cache="hit", attempt=0, output=clip)
            ctx.status(shot.id, "cached", clip)
            continue

        waiting.append(shot.id)
        if shot.fallback == "none":
            ctx.status(shot.id, "waiting", note="no fallback; needs a GPU clip")
            continue

        fallback = fallback_path(outputs_dir, shot, storyboard)
        local_call = Call(stage=STAGE, provider="local", model=f"ffmpeg-{shot.fallback}", shot=shot.id)
        if fallback.exists() and not ctx.force:
            ctx.log.record(local_call, status="fallback", cache="hit", attempt=0, output=fallback)
            ctx.status(shot.id, "fallback", fallback, "cached")
            continue
        if ctx.dry_run:
            ctx.status(shot.id, "would generate", fallback, shot.fallback)
            continue

        with atomic_output(fallback) as temporary:
            call_with_retry(
                lambda: render_kenburns(keyframe, temporary, shot.camera, shot.duration_s, still=shot.fallback == "still"),
                call=local_call,
                log=ctx.log,
                max_attempts=1,
                output=fallback,
            )
        ctx.status(shot.id, "fallback", fallback, "rendered")

    if waiting:
        ctx.console.print(
            f"  [yellow]{len(waiting)} shot(s) wait for a GPU clip:[/] {', '.join(waiting)}. "
            "Run: heritage gpu export shots"
        )
