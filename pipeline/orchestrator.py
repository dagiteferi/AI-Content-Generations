from collections.abc import Callable

from pipeline.context import StageContext
from pipeline.stages import narration, radio

Stage = Callable[[StageContext], None]

STAGES: dict[str, Stage] = {
    "narration": narration.run,
    "radio": radio.run,
}


def run_stages(ctx: StageContext, names: list[str] | None = None) -> None:
    selected = names or list(STAGES)
    unknown = [name for name in selected if name not in STAGES]
    if unknown:
        raise ValueError(f"Unknown stage(s): {', '.join(unknown)}. Available: {', '.join(STAGES)}")

    for name in STAGES:
        if name in selected:
            ctx.console.rule(f"[bold]{name}")
            STAGES[name](ctx)
