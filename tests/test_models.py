import pytest
from pydantic import ValidationError

from pipeline.models import Storyboard


def test_sample_storyboard_is_valid(storyboard_data):
    storyboard = Storyboard.model_validate(storyboard_data)
    assert 60 <= storyboard.planned_duration_s <= 90


def test_rejects_too_few_shots(storyboard_data):
    storyboard_data["shots"] = storyboard_data["shots"][:7]
    with pytest.raises(ValidationError, match="at least 8"):
        Storyboard.model_validate(storyboard_data)


def test_rejects_duplicate_shot_ids(storyboard_data):
    storyboard_data["shots"][1]["id"] = "s01"
    with pytest.raises(ValidationError, match="Duplicate shot ids"):
        Storyboard.model_validate(storyboard_data)


def test_rejects_unknown_character(storyboard_data):
    storyboard_data["shots"][0]["characters"] = ["grandfather"]
    with pytest.raises(ValidationError, match="unknown characters"):
        Storyboard.model_validate(storyboard_data)


def test_rejects_film_longer_than_90_seconds(storyboard_data):
    for shot in storyboard_data["shots"]:
        shot["duration_s"] = 12
    with pytest.raises(ValidationError, match="must be 60-90s"):
        Storyboard.model_validate(storyboard_data)


def test_real_person_requires_consent_ref(storyboard_data):
    storyboard_data["characters"][0]["real_person"] = True
    with pytest.raises(ValidationError, match="no consent_ref"):
        Storyboard.model_validate(storyboard_data)


def test_rejects_unknown_fields(storyboard_data):
    storyboard_data["shots"][0]["mood"] = "happy"
    with pytest.raises(ValidationError, match="Extra inputs"):
        Storyboard.model_validate(storyboard_data)
