import json
from pathlib import Path

from pipeline.errors import ConsentError
from pipeline.models import Storyboard


def load_storyboard(path: Path) -> Storyboard:
    return Storyboard.model_validate_json(path.read_text(encoding="utf-8"))


def save_storyboard(storyboard: Storyboard, path: Path) -> None:
    payload = storyboard.model_dump(mode="json")
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def storyboard_schema() -> dict:
    schema = Storyboard.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["title"] = "Heritage Short storyboard"
    return schema


def export_schema(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(storyboard_schema(), indent=2) + "\n", encoding="utf-8")


def missing_consent(storyboard: Storyboard, ethics_path: Path) -> list[str]:
    records = ethics_path.read_text(encoding="utf-8") if ethics_path.exists() else ""
    return [
        character.id
        for character in storyboard.characters
        if character.real_person and f"consent:{character.consent_ref}" not in records
    ]


def ensure_consent(storyboard: Storyboard, ethics_path: Path) -> None:
    missing = missing_consent(storyboard, ethics_path)
    if missing:
        raise ConsentError(
            f"No consent record in {ethics_path.name} for: {', '.join(missing)}. "
            "Add a row tagged `consent:<consent_ref>` before generating anything of them."
        )
