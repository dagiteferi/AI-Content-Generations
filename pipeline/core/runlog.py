import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

Status = Literal["ok", "error", "fallback"]
CacheState = Literal["hit", "miss"]


@dataclass(frozen=True)
class Call:
    stage: str
    provider: str
    model: str
    shot: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    seed: int | None = None


class RunLog:
    """Appends one JSON line per model call to runs.jsonl."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.run_id = datetime.now(UTC).strftime("r-%Y%m%d-%H%M%S")

    def record(
        self,
        call: Call,
        *,
        status: Status,
        cache: CacheState = "miss",
        attempt: int = 1,
        latency_s: float = 0.0,
        output: Path | None = None,
        error: str | None = None,
        gpu_s: float | None = None,
        cost_usd_list: float | None = None,
    ) -> None:
        entry = {
            "ts": datetime.now(UTC).isoformat(timespec="seconds"),
            "run_id": self.run_id,
            "stage": call.stage,
            "shot": call.shot,
            "provider": call.provider,
            "model": call.model,
            "params": call.params,
            "seed": call.seed,
            "cache": cache,
            "attempt": attempt,
            "latency_s": round(latency_s, 3),
            "gpu_s": gpu_s,
            "cost_usd_list": cost_usd_list,
            "status": status,
            "error": error,
            "output": self._relative(output),
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _relative(self, output: Path | None) -> str | None:
        if output is None:
            return None
        try:
            return str(output.resolve().relative_to(self.path.resolve().parent))
        except ValueError:
            return str(output)
