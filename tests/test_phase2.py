import json
import zipfile

import pytest

from pipeline.config import Settings
from pipeline.core.runlog import RunLog
from pipeline.errors import StageError
from pipeline.gpu import export_bundle, import_results, shot_jobs
from pipeline.models import Storyboard
from pipeline.prompts import keyframe_prompt
from pipeline.providers.kenburns import motion_expressions
from pipeline.stages import music, shots
from pipeline.stages.keyframes import keyframe_path


@pytest.fixture
def storyboard(storyboard_data) -> Storyboard:
    return Storyboard.model_validate(storyboard_data)


@pytest.fixture
def settings(tmp_path) -> Settings:
    kaggle = tmp_path / "kaggle"
    kaggle.mkdir()
    for script in ("runner.py", "wan_shots.py", "acestep_music.py"):
        (kaggle / script).write_text("# stub\n")
    return Settings(root=tmp_path, _env_file=None)


def write_keyframes(settings: Settings, storyboard: Storyboard) -> None:
    for shot in storyboard.shots:
        path = keyframe_path(settings.outputs_dir, shot, storyboard)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"jpeg")


def test_keyframe_prompt_carries_character_and_style(storyboard):
    shot = storyboard.shot("s02")
    prompt = keyframe_prompt(shot, storyboard)
    assert storyboard.characters[0].description in prompt
    assert prompt.endswith(storyboard.style_block)


def test_style_block_change_invalidates_every_keyframe(storyboard_data, tmp_path):
    before = Storyboard.model_validate(storyboard_data)
    storyboard_data["style_block"] = "charcoal sketch on rough paper, high contrast"
    after = Storyboard.model_validate(storyboard_data)
    assert all(
        keyframe_path(tmp_path, a, before) != keyframe_path(tmp_path, b, after)
        for a, b in zip(before.shots, after.shots)
    )


def test_new_keyframe_invalidates_its_clip_only(storyboard_data, tmp_path):
    before = Storyboard.model_validate(storyboard_data)
    storyboard_data["shots"][4]["keyframe"]["seed"] = 999
    after = Storyboard.model_validate(storyboard_data)
    changed = [
        a.id
        for a, b in zip(before.shots, after.shots)
        if shots.clip_path(tmp_path, a, before) != shots.clip_path(tmp_path, b, after)
    ]
    assert changed == ["s05"]


@pytest.mark.parametrize(
    ("camera", "zoom_moves", "x_moves", "y_moves"),
    [
        ("locked-off", False, False, False),
        ("slow push-in", True, False, False),
        ("slow pull-back", True, False, False),
        ("slow pan right", False, True, False),
        ("slow tilt down", False, False, True),
    ],
)
def test_kenburns_follows_camera_note(camera, zoom_moves, x_moves, y_moves):
    zoom, x, y = motion_expressions(camera, frames=192)
    assert ("on/" in zoom) == zoom_moves
    assert ("on/" in x) == x_moves
    assert ("on/" in y) == y_moves


def test_motion_frames_must_be_4k_plus_1(storyboard_data):
    storyboard_data["shots"][0]["motion"]["frames"] = 120
    with pytest.raises(ValueError, match="4k\\+1"):
        Storyboard.model_validate(storyboard_data)


def test_chosen_seed_must_be_a_candidate(storyboard_data):
    storyboard_data["music"]["chosen_seed"] = 7
    with pytest.raises(ValueError, match="not one of music.seeds"):
        Storyboard.model_validate(storyboard_data)


def test_export_requires_keyframes(settings, storyboard):
    with pytest.raises(StageError, match="Keyframes missing"):
        export_bundle(settings, storyboard, "shots")


def test_export_bundle_contains_jobs_images_and_scripts(settings, storyboard):
    write_keyframes(settings, storyboard)
    archive, count = export_bundle(settings, storyboard, "shots")
    names = zipfile.ZipFile(archive).namelist()
    assert count == len(storyboard.shots)
    assert {"jobs.json", "runner.py", "wan_shots.py"} <= set(names)
    assert sum(name.startswith("images/") and name.endswith(".jpg") for name in names) == count


def test_import_accepts_expected_outputs_and_rejects_stale(settings, storyboard):
    write_keyframes(settings, storyboard)
    job = shot_jobs(settings, storyboard)[0]
    out = settings.root / "out"
    out.mkdir()
    (out / job["output"]).write_bytes(b"clip")
    (out / "s01.000000000000.mp4").write_bytes(b"old")
    lines = [
        {"kind": "shots", "id": "s01", "output": "s01.000000000000.mp4", "status": "ok", "seconds": 1},
        {"kind": "shots", "id": "s01", "output": job["output"], "status": "error", "seconds": 5, "error": "OOM"},
        {"kind": "shots", "id": "s01", "output": job["output"], "status": "ok", "seconds": 300},
    ]
    (out / "results.jsonl").write_text("\n".join(json.dumps(line) for line in lines))

    log = RunLog(settings.root / "runs.jsonl")
    summary = import_results(settings, storyboard, out, log)

    assert summary.imported == ["s01"]
    assert summary.stale == ["s01.000000000000.mp4"]
    assert summary.failed == []
    assert shots.resolve_clip(settings.outputs_dir, storyboard.shot("s01"), storyboard).name == job["output"]
    entry = json.loads(log.path.read_text().splitlines()[-1])
    assert entry["provider"] == "kaggle" and entry["gpu_s"] == 300


def test_music_candidates_share_a_key_and_differ_by_seed(storyboard, tmp_path):
    cue = storyboard.music.cues[0]
    paths = [music.candidate_path(tmp_path, cue, storyboard.music, seed) for seed in storyboard.music.seeds]
    keys = {path.name.split(".")[1] for path in paths}
    assert len(keys) == 1
    assert len(set(paths)) == len(storyboard.music.seeds)
