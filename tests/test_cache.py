from pipeline.core.cache import atomic_write_bytes, cache_key
from pipeline.models import Storyboard
from pipeline.stages.narration import narration_path


def test_cache_key_ignores_key_order():
    assert cache_key({"a": 1, "b": [1, 2]}) == cache_key({"b": [1, 2], "a": 1})


def test_cache_key_changes_with_content():
    assert cache_key({"text": "one"}) != cache_key({"text": "two"})


def test_changing_one_line_changes_only_that_narration_path(storyboard_data, tmp_path):
    before = Storyboard.model_validate(storyboard_data)
    storyboard_data["shots"][2]["narration"]["text"] = "A different line."
    after = Storyboard.model_validate(storyboard_data)

    changed = [
        old.id
        for old, new in zip(before.shots, after.shots)
        if narration_path(tmp_path, old, before.voice) != narration_path(tmp_path, new, after.voice)
    ]
    assert changed == ["s03"]


def test_atomic_write_leaves_no_temporary_file(tmp_path):
    target = tmp_path / "out" / "file.bin"
    atomic_write_bytes(target, b"data")
    assert target.read_bytes() == b"data"
    assert [p.name for p in target.parent.iterdir()] == ["file.bin"]


def test_network_errors_from_other_httpx_copies_are_transient():
    from pipeline.core.retry import is_transient

    class TransportError(Exception):
        pass

    class ReadTimeout(TransportError):
        pass

    assert is_transient(ReadTimeout("timed out"))
    assert not is_transient(ValueError("bad input"))
