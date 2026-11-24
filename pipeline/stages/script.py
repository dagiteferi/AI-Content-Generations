import json

from pydantic import ValidationError

from pipeline.core.retry import call_with_retry
from pipeline.core.runlog import Call, RunLog
from pipeline.errors import StageError
from pipeline.models import MAX_FILM_S, MAX_SHOTS, MIN_FILM_S, MIN_SHOTS, Storyboard
from pipeline.providers.base import TextModel
from pipeline.storyboard import storyboard_schema

STAGE = "script"
MAX_REPAIRS = 3

INSTRUCTIONS = f"""\
You are a film pre-production assistant. Turn the story brief below into a storyboard
for a {MIN_FILM_S:.0f}-{MAX_FILM_S:.0f} second vertical short film.

Rules:
- {MIN_SHOTS}-{MAX_SHOTS} shots with ids s01, s02, ... Shot durations plus the end card
  must total between {MIN_FILM_S:.0f} and {MAX_FILM_S:.0f} seconds.
- Narration is written for the ear: short sentences, concrete images. Budget about
  2 words per second of shot duration. `text` is in the narration language from the
  brief; `subtitle` is its faithful English translation.
- Every shot states its `purpose`: why the film needs it.
- Vary shot sizes: establish with wide shots, use close-ups for feeling.
- One idea and one gentle movement per shot.
- `keyframe.prompt` describes subject, setting, composition and light. Keep the subject
  centred so the frame can be cropped to 16:9. Never ask for text or signs in the image.
- `motion.prompt` describes only the motion and the camera, never the subject again.
- `style_block` is one line describing the look (medium, palette, light), with no artist names.
- Use distinct integer seeds. Mark anyone from real life as `real_person: true` and set
  `consent_ref` to their character id.
- The end card says the film was made with AI.

Return only JSON that validates against this JSON Schema:
"""


def build_prompt(brief: str) -> str:
    schema = json.dumps(storyboard_schema(), ensure_ascii=False)
    return f"{INSTRUCTIONS}{schema}\n\nStory brief:\n{brief.strip()}\n"


def repair_prompt(prompt: str, answer: str, error: ValidationError | ValueError) -> str:
    return (
        f"{prompt}\nYour previous answer:\n{answer}\n\n"
        f"It failed validation:\n{error}\n\nReturn the corrected JSON only."
    )


def draft_storyboard(
    brief: str,
    model: TextModel,
    log: RunLog,
    max_attempts: int = 3,
) -> Storyboard:
    prompt = build_prompt(brief)
    call = Call(stage=STAGE, provider=model.provider, model=model.model)

    for _ in range(MAX_REPAIRS):
        answer = call_with_retry(
            lambda: model.generate_json(prompt),
            call=call,
            log=log,
            max_attempts=max_attempts,
        )
        try:
            return Storyboard.model_validate_json(answer)
        except ValidationError as error:
            prompt = repair_prompt(build_prompt(brief), answer, error)

    raise StageError(f"The model did not produce a valid storyboard after {MAX_REPAIRS} tries")
