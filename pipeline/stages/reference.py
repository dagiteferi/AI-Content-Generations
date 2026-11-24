"""Character reference candidates. Approve one with `heritage approve-reference`."""

from pathlib import Path

from pipeline.context import StageContext
from pipeline.core.cache import atomic_write_bytes, cache_key
from pipeline.core.retry import call_with_retry
from pipeline.core.runlog import Call
from pipeline.models import DEFAULT_IMAGE_MODEL, Character, Storyboard
from pipeline.prompts import reference_prompt
from pipeline.providers.base import ImageModel
from pipeline.providers.factory import image_model

STAGE = "reference"


def candidate_path(outputs_dir: Path, character: Character, storyboard: Storyboard, seed: int) -> Path:
    key = cache_key(
        {
            "stage": STAGE,
            "model": DEFAULT_IMAGE_MODEL,
            "prompt": reference_prompt(character, storyboard),
            "seed": seed,
        }
    )
    return outputs_dir / STAGE / f"{character.id}.seed{seed}.{key}.jpg"


def run(ctx: StageContext) -> None:
    storyboard = ctx.storyboard
    if not storyboard.characters:
        ctx.status("-", "skipped", note="no characters in the storyboard")
        return

    model: ImageModel | None = None
    for character in storyboard.characters:
        prompt = reference_prompt(character, storyboard)
        for seed in character.reference_seeds:
            path = candidate_path(ctx.settings.outputs_dir, character, storyboard, seed)
            call = Call(stage=STAGE, provider="cloudflare", model=DEFAULT_IMAGE_MODEL, shot=character.id, seed=seed)

            if path.exists() and not ctx.force:
                ctx.log.record(call, status="ok", cache="hit", attempt=0, output=path)
                ctx.status(character.id, "cached", path)
                continue
            if ctx.dry_run:
                ctx.status(character.id, "would generate", path)
                continue

            model = model or image_model(ctx.settings, DEFAULT_IMAGE_MODEL)
            generator = model
            image = call_with_retry(
                lambda: generator.generate(prompt, seed=seed),
                call=call,
                log=ctx.log,
                max_attempts=ctx.settings.max_attempts,
                output=path,
            )
            atomic_write_bytes(path, image)
            ctx.status(character.id, "generated", path)

        if not character.reference_image:
            ctx.console.print(
                f"  [yellow]approve one:[/] heritage approve-reference {character.id} "
                f"<seed>  (seeds: {', '.join(map(str, character.reference_seeds))})"
            )
