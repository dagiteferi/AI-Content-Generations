from pathlib import Path

from pipeline.context import StageContext
from pipeline.core.cache import atomic_write_bytes, cache_key
from pipeline.core.media import audio_duration_s
from pipeline.core.retry import call_with_retry
from pipeline.core.runlog import Call
from pipeline.models import Shot, Voice
from pipeline.providers.base import SpeechModel
from pipeline.providers.gemini import GeminiSpeech

STAGE = "narration"


def narration_path(outputs_dir: Path, shot: Shot, voice: Voice) -> Path:
    key = cache_key(
        {
            "stage": STAGE,
            "model": voice.model,
            "voice": voice.voice_name,
            "style": voice.style,
            "text": shot.narration.text,
        }
    )
    return outputs_dir / STAGE / f"{shot.id}.{key}.wav"


def run(ctx: StageContext) -> None:
    voice = ctx.storyboard.voice
    speech: SpeechModel | None = None

    for shot in ctx.selected_shots():
        path = narration_path(ctx.settings.outputs_dir, shot, voice)
        call = Call(
            stage=STAGE,
            provider="gemini",
            model=voice.model,
            shot=shot.id,
            params={"voice": voice.voice_name, "style": voice.style},
        )

        if path.exists() and not ctx.force:
            ctx.log.record(call, status="ok", cache="hit", attempt=0, output=path)
            ctx.status(shot.id, "cached", path, f"{audio_duration_s(path):.1f}s")
            continue

        if ctx.dry_run:
            ctx.status(shot.id, "would generate", path)
            continue

        if speech is None:
            speech = GeminiSpeech(ctx.settings.secret("gemini_api_key"), voice.model)
        model = speech

        audio = call_with_retry(
            lambda: model.synthesize(shot.narration.text, voice=voice.voice_name, style=voice.style),
            call=call,
            log=ctx.log,
            max_attempts=ctx.settings.max_attempts,
            output=path,
        )
        atomic_write_bytes(path, audio)
        ctx.status(shot.id, "generated", path, f"{audio_duration_s(path):.1f}s")
