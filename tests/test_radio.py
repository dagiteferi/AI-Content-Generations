from pipeline.models import Storyboard
from pipeline.stages.radio import (
    NARRATION_TAIL_S,
    SUBTITLE_LINES,
    SUBTITLE_WIDTH,
    plan_timeline,
    srt_timestamp,
    subtitle_chunks,
    subtitle_cues,
)


def test_slot_extends_when_narration_is_longer_than_planned(storyboard_data):
    storyboard = Storyboard.model_validate(storyboard_data)
    durations = {shot.id: 3.0 for shot in storyboard.shots}
    durations["s02"] = 10.0

    slots = plan_timeline(storyboard, durations)

    assert slots[0].length_s == storyboard.shots[0].duration_s
    assert slots[1].length_s == 10.0 + NARRATION_TAIL_S
    assert slots[1].overrun_s > 0
    assert slots[2].start_s == slots[1].end_s


def test_subtitle_chunks_respect_width_and_lines():
    text = "Three cups, she told me. The first for talk, the second for thought, the third for blessing."
    for chunk in subtitle_chunks(text):
        lines = chunk.split("\n")
        assert len(lines) <= SUBTITLE_LINES
        assert all(len(line) <= SUBTITLE_WIDTH for line in lines)


def test_cues_stay_inside_spoken_time(storyboard_data):
    storyboard = Storyboard.model_validate(storyboard_data)
    slots = plan_timeline(storyboard, {shot.id: 4.0 for shot in storyboard.shots})
    cues = subtitle_cues(slots)
    for slot in slots:
        mine = [c for c in cues if slot.start_s <= c.start_s < slot.end_s]
        assert mine[-1].end_s <= slot.start_s + slot.narration_s + 1e-9


def test_srt_timestamp_format():
    assert srt_timestamp(3725.5) == "01:02:05,500"
