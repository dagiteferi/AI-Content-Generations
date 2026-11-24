"""Score candidates made on Kaggle with ACE-Step; the storyboard records the choice."""

from pathlib import Path

from pipeline.context import StageContext
from pipeline.core.cache import cache_key
from pipeline.core.runlog import Call
from pipeline.models import Music, MusicCue

STAGE = "music"


def candidate_path(outputs_dir: Path, cue: MusicCue, music: Music, seed: int) -> Path:
    key = cache_key(
        {
            "stage": STAGE,
            "model": music.model,
            "caption": cue.caption,
            "duration_s": cue.end_s - cue.start_s,
            "bpm": cue.bpm,
            "key": cue.key,
            "instrumental": cue.instrumental,
        }
    )
    return outputs_dir / STAGE / f"{cue.id}.{key}.seed{seed}.wav"


def chosen_track(outputs_dir: Path, music: Music, cue: MusicCue) -> Path | None:
    if music.chosen_seed is None:
        return None
    path = candidate_path(outputs_dir, cue, music, music.chosen_seed)
    return path if path.exists() else None


def run(ctx: StageContext) -> None:
    music = ctx.storyboard.music
    if not music.cues:
        ctx.status("-", "skipped", note="no music cues in the storyboard")
        return

    missing = 0
    for cue in music.cues:
        for seed in music.seeds:
            path = candidate_path(ctx.settings.outputs_dir, cue, music, seed)
            label = f"{cue.id}#{seed}"
            if path.exists():
                call = Call(stage=STAGE, provider="kaggle", model=music.model, shot=cue.id, seed=seed)
                ctx.log.record(call, status="ok", cache="hit", attempt=0, output=path)
                chosen = " (chosen)" if seed == music.chosen_seed else ""
                ctx.status(label, "cached", path, chosen)
            else:
                missing += 1
                ctx.status(label, "waiting", path, "needs GPU")

    if missing:
        ctx.console.print(f"  [yellow]{missing} candidate(s) missing.[/] Run: heritage gpu export music")
    elif music.chosen_seed is None:
        ctx.console.print(
            "  [yellow]listen to the candidates under the narration,[/] then set "
            "music.chosen_seed and music.choice_reason in storyboard.json"
        )
