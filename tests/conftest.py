import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def storyboard_data() -> dict:
    return json.loads((ROOT / "storyboard.json").read_text(encoding="utf-8"))
