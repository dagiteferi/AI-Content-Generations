import pytest

from pipeline.errors import ConsentError
from pipeline.models import Storyboard
from pipeline.storyboard import ensure_consent, missing_consent


@pytest.fixture
def real_person_storyboard(storyboard_data) -> Storyboard:
    storyboard_data["characters"][0]["real_person"] = True
    storyboard_data["characters"][0]["consent_ref"] = "grandmother"
    return Storyboard.model_validate(storyboard_data)


def test_missing_consent_is_reported(real_person_storyboard, tmp_path):
    ethics = tmp_path / "ETHICS.md"
    ethics.write_text("# Ethics\n", encoding="utf-8")
    assert missing_consent(real_person_storyboard, ethics) == [real_person_storyboard.characters[0].id]
    with pytest.raises(ConsentError):
        ensure_consent(real_person_storyboard, ethics)


def test_recorded_consent_passes(real_person_storyboard, tmp_path):
    ethics = tmp_path / "ETHICS.md"
    ethics.write_text("| Grandmother | voice | consent:grandmother |\n", encoding="utf-8")
    ensure_consent(real_person_storyboard, ethics)
