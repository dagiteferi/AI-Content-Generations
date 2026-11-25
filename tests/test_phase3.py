import json
from pathlib import Path

import pytest

from pipeline.models import Storyboard
from pipeline.report import markdown_table, summarise, write_into
from pipeline.stages.assemble import (
    RATIOS,
    ClipInput,
    ass_time,
    crop_scale,
    picture_command,
    place_cues,
    premix_command,
    shot_filter,
    to_ass,
)
from pipeline.stages.radio import Cue, plan_timeline


@pytest.fixture
def storyboard(storyboard_data) -> Storyboard:
    return Storyboard.model_validate(storyboard_data)


@pytest.fixture
def slots(storyboard):
    return plan_timeline(storyboard, {shot.id: 3.0 for shot in storyboard.shots})


def test_both_ratios_are_exported():
    assert {(r.width, r.height) for r in RATIOS} == {(1080, 1920), (1920, 1080)}


def test_vertical_subtitles_sit_above_platform_buttons():
    vertical = next(r for r in RATIOS if r.name == "9x16")
    assert vertical.margin_v >= 0.2 * vertical.height


def test_crop_keeps_the_centre_for_each_ratio():
    for ratio in RATIOS:
        chain = crop_scale(ratio)
        assert f"scale={ratio.width}:{ratio.height}" in chain
        assert "crop=w='min(iw,ih*" in chain


def test_short_clip_is_stretched_then_held(slots):
    slot = slots[0]
    clip = ClipInput(Path("s01.abc.mp4"), duration_s=5.0, generated=True)
    chain = shot_filter(0, clip, slot, RATIOS[0], last=False)
    assert "trim=start=0.250" in chain
    assert "tpad=stop_mode=clone" in chain
    assert f"trim=duration={slot.length_s:.3f}" in chain
    assert "fade=t=in" in chain


def test_fallback_clip_is_not_head_trimmed(slots):
    clip = ClipInput(Path("s02.abc.kenburns.mp4"), duration_s=slots[1].length_s, generated=False)
    assert "trim=start=0.000" in shot_filter(1, clip, slots[1], RATIOS[1], last=True)


def test_cues_follow_the_stretched_timeline(storyboard, storyboard_data):
    long = {shot.id: shot.duration_s * 2 for shot in storyboard.shots}
    slots = plan_timeline(storyboard, long)
    (start, end), = place_cues(storyboard, slots)
    cue = storyboard.music.cues[0]
    assert start == cue.start_s
    assert end > cue.end_s


def test_premix_uses_placeholder_without_a_chosen_score(slots):
    files = [Path(f"n{i}.wav") for i in range(len(slots))]
    command = premix_command(files, slots, 3.0, None, [(0, 60)], Path("out.wav"))
    graph = command[command.index("-filter_complex") + 1]
    assert "sine=frequency" in graph
    assert "sidechaincompress" in graph


def test_premix_places_the_chosen_track(slots):
    files = [Path(f"n{i}.wav") for i in range(len(slots))]
    command = premix_command(files, slots, 3.0, [Path("score.wav")], [(0.0, 60.0)], Path("out.wav"))
    graph = command[command.index("-filter_complex") + 1]
    assert "score.wav" in command
    assert f"[{len(files)}:a]" in graph
    assert "sine=frequency" not in graph


def test_picture_command_maps_every_clip_and_the_mix(slots, tmp_path):
    clips = [ClipInput(Path(f"{s.shot_id}.mp4"), 5.0, True) for s in slots]
    command = picture_command(clips, slots, RATIOS[0], 3.0, tmp_path / "subs.ass", Path("mix.wav"), Path("o.mp4"))
    assert command.count("-i") == len(clips) + 2
    graph = command[command.index("-filter_complex") + 1]
    assert f"concat=n={len(clips) + 1}" in graph
    assert "subtitles=filename=" in graph


def test_ass_has_frame_sized_canvas_and_end_card():
    ratio = RATIOS[0]
    text = to_ass([Cue(0.0, 2.5, "Line one\nline two")], ratio, "Made with AI from a family story", 60.0, 63.0)
    assert f"PlayResX: {ratio.width}" in text and f"PlayResY: {ratio.height}" in text
    assert "Line one\\Nline two" in text
    assert "Made with AI" in text and "0:01:00.00" in text


def test_ass_time_format():
    assert ass_time(3725.5) == "1:02:05.50"


def write_runs(path: Path, entries: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n")


def test_costs_count_calls_hits_and_gpu(tmp_path):
    runs = tmp_path / "runs.jsonl"
    write_runs(runs, [
        {"stage": "narration", "provider": "gemini", "cache": "miss", "status": "ok", "latency_s": 2.0},
        {"stage": "narration", "provider": "gemini", "cache": "hit", "status": "ok", "latency_s": 0},
        {"stage": "shots", "provider": "kaggle", "cache": "miss", "status": "ok", "latency_s": 600, "gpu_s": 600},
        {"stage": "shots", "provider": "kaggle", "cache": "miss", "status": "error", "latency_s": 30},
    ])
    stages = summarise(runs)
    assert stages["narration"].calls == 1 and stages["narration"].cache_hits == 1
    assert stages["shots"].errors == 1
    assert stages["shots"].gpu_s == 600
    assert "| **Total** | 3 | 1 | 1 |" in markdown_table(stages)


def test_costs_are_written_between_markers(tmp_path):
    doc = tmp_path / "COSTS.md"
    doc.write_text("intro\n<!-- costs:start -->\nold\n<!-- costs:end -->\noutro\n")
    write_into(doc, "| new |")
    text = doc.read_text()
    assert "| new |" in text and "old" not in text and text.endswith("outro\n")


def test_silent_shots_get_silence_and_no_subtitle(storyboard_data):
    from pipeline.stages.radio import voice_graph

    storyboard_data["shots"][0]["narration"] = None
    storyboard = Storyboard.model_validate(storyboard_data)
    spoken = {s.id: 3.0 for s in storyboard.shots if s.narration}
    slots = plan_timeline(storyboard, spoken)

    assert slots[0].length_s == storyboard.shots[0].duration_s
    assert all(cue.start_s >= slots[0].end_s for cue in __import__("pipeline.stages.radio", fromlist=["x"]).subtitle_cues(slots))

    files = [None if s.narration is None else Path(f"{s.id}.wav") for s in storyboard.shots]
    inputs, parts = voice_graph(files, slots, 3.0)
    assert inputs.count("-i") == sum(1 for s in storyboard.shots if s.narration)
    assert parts[0].startswith("anullsrc") and parts[1].startswith("[0:a]")
