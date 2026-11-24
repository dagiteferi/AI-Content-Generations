from pathlib import Path

from pipeline.context import StageContext
from pipeline.core.cache import atomic_write_bytes, cache_key
from pipeline.core.retry import call_with_retry
from pipeline.core.runlog import Call
from pipeline.models import Shot, Storyboard
from pipeline.prompts import keyframe_prompt
from pipeline.providers.base import ImageModel
from pipeline.providers.factory import image_model

STAGE = "keyframes"


def keyframe_path(outputs_dir: Path, shot: Shot, storyboard: Storyboard) -> Path:
    key = cache_key(
        {
            "stage": STAGE,
            "model": shot.keyframe.model,
            "prompt": keyframe_prompt(shot, storyboard),
            "seed": shot.keyframe.seed,
        }
    )
    return outputs_dir / STAGE / f"{shot.id}.{key}.jpg"


def run(ctx: StageContext) -> None:
    storyboard = ctx.storyboard
    models: dict[str, ImageModel] = {}

    for shot in ctx.selected_shots():
        path = keyframe_path(ctx.settings.outputs_dir, shot, storyboard)
        prompt = keyframe_prompt(shot, storyboard)
        call = Call(
            stage=STAGE,
            provider="cloudflare",
            model=shot.keyframe.model,
            shot=shot.id,
            params={"prompt": prompt},
            seed=shot.keyframe.seed,
        )

        if path.exists() and not ctx.force:
            ctx.log.record(call, status="ok", cache="hit", attempt=0, output=path)
            ctx.status(shot.id, "cached", path)
            continue
        if ctx.dry_run:
            ctx.status(shot.id, "would generate", path)
            continue

        if shot.keyframe.model not in models:
            models[shot.keyframe.model] = image_model(ctx.settings, shot.keyframe.model)
        generator = models[shot.keyframe.model]

        image = call_with_retry(
            lambda: generator.generate(prompt, seed=shot.keyframe.seed),
            call=call,
            log=ctx.log,
            max_attempts=ctx.settings.max_attempts,
            output=path,
        )
        atomic_write_bytes(path, image)
        ctx.status(shot.id, "generated", path)
