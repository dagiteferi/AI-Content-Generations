import hashlib
import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

KEY_LENGTH = 12


def cache_key(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:KEY_LENGTH]


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()[:KEY_LENGTH]


@contextmanager
def atomic_output(path: Path) -> Iterator[Path]:
    """Yield a temporary path that replaces `path` only if the block succeeds."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.stem}.tmp{path.suffix}")
    try:
        yield temporary
        if not temporary.exists() or temporary.stat().st_size == 0:
            raise RuntimeError(f"No output was written for {path.name}")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_write_bytes(path: Path, data: bytes) -> None:
    with atomic_output(path) as temporary:
        temporary.write_bytes(data)
