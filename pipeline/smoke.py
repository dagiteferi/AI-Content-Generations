import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from pipeline.config import Settings
from pipeline.core.cache import atomic_write_bytes
from pipeline.core.media import audio_duration_s, ffmpeg_version
from pipeline.core.retry import call_with_retry, describe
from pipeline.core.runlog import Call, RunLog
from pipeline.models import DEFAULT_IMAGE_MODEL, DEFAULT_TTS_MODEL
from pipeline.providers.cloudflare import CloudflareFlux
from pipeline.providers.gemini import GeminiSpeech, GeminiText
from pipeline.providers.kaggle import KaggleAccount

STAGE = "smoke"


@dataclass(frozen=True)
class Check:
    name: str
    provider: str
    model: str
    probe: Callable[[], str]


@dataclass(frozen=True)
class SmokeResult:
    name: str
    model: str
    ok: bool
    latency_s: float
    detail: str


def _gemini_text(settings: Settings) -> str:
    model = GeminiText(settings.secret("gemini_api_key"), settings.text_model)
    return model.generate_json('Reply with {"status": "ready"}').strip()


def _gemini_tts(settings: Settings, out_dir: Path) -> str:
    model = GeminiSpeech(settings.secret("gemini_api_key"), DEFAULT_TTS_MODEL)
    path = out_dir / "tts.wav"
    atomic_write_bytes(path, model.synthesize("ሰላም። እንኳን ደህና መጣችሁ።", voice="Sulafat", style="warm"))
    return f"{audio_duration_s(path):.1f}s of audio -> {path.name}"


def _cloudflare_flux(settings: Settings, out_dir: Path) -> str:
    model = CloudflareFlux(
        settings.secret("cloudflare_account_id"),
        settings.secret("cloudflare_api_token"),
    )
    path = out_dir / "flux.jpg"
    atomic_write_bytes(path, model.generate("a clay coffee pot on a wooden table, morning light", seed=1))
    return f"{path.stat().st_size // 1024} KB image -> {path.name}"


def _kaggle(settings: Settings) -> str:
    if settings.kaggle_api_token:
        return KaggleAccount(api_token=settings.secret("kaggle_api_token")).check()
    return KaggleAccount(username=settings.secret("kaggle_username"), key=settings.secret("kaggle_key")).check()


def checks(settings: Settings, out_dir: Path) -> list[Check]:
    return [
        Check("gemini text", "gemini", settings.text_model, lambda: _gemini_text(settings)),
        Check("gemini tts", "gemini", DEFAULT_TTS_MODEL, lambda: _gemini_tts(settings, out_dir)),
        Check("cloudflare flux", "cloudflare", DEFAULT_IMAGE_MODEL, lambda: _cloudflare_flux(settings, out_dir)),
        Check("kaggle", "kaggle", "api", lambda: _kaggle(settings)),
        Check("ffmpeg", "local", "ffmpeg", ffmpeg_version),
    ]


def run_smoke(settings: Settings, log: RunLog) -> list[SmokeResult]:
    out_dir = settings.outputs_dir / STAGE
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[SmokeResult] = []

    for check in checks(settings, out_dir):
        call = Call(stage=STAGE, provider=check.provider, model=check.model)
        started = time.perf_counter()
        try:
            detail = call_with_retry(check.probe, call=call, log=log, max_attempts=1)
            ok = True
        except Exception as error:
            detail, ok = describe(error), False
        results.append(SmokeResult(check.name, check.model, ok, time.perf_counter() - started, detail))

    return results
