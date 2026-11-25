"""Turn runs.jsonl into a cost table per stage."""

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

# Rough paid prices, so we can say what the free run would have cost.
GPU_USD_PER_HOUR = 0.35  # one T4
USD_PER_CALL = {
    "gemini": 0.002,
    "cloudflare": 0.0011,
}

START = "<!-- costs:start -->"
END = "<!-- costs:end -->"


@dataclass
class StageCost:
    calls: int = 0
    cache_hits: int = 0
    errors: int = 0
    latencies: list[float] = field(default_factory=list)
    gpu_s: float = 0.0
    usd: float = 0.0

    @property
    def mean_latency_s(self) -> float:
        if not self.latencies:
            return 0.0
        return sum(self.latencies) / len(self.latencies)

    def add(self, other: "StageCost") -> None:
        self.calls += other.calls
        self.cache_hits += other.cache_hits
        self.errors += other.errors
        self.gpu_s += other.gpu_s
        self.usd += other.usd


def price(entry: dict) -> float:
    if entry.get("cost_usd_list") is not None:
        return float(entry["cost_usd_list"])
    if entry.get("gpu_s"):
        return entry["gpu_s"] / 3600 * GPU_USD_PER_HOUR
    return USD_PER_CALL.get(entry.get("provider", ""), 0.0)


def summarise(runs: Path) -> dict[str, StageCost]:
    if not runs.exists():
        return {}

    stages: dict[str, StageCost] = defaultdict(StageCost)
    for line in runs.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        stage = stages[entry["stage"]]

        # A cache hit made no call, so it costs nothing.
        if entry.get("cache") == "hit":
            stage.cache_hits += 1
            continue

        stage.calls += 1
        stage.latencies.append(entry.get("latency_s") or 0.0)
        stage.gpu_s += entry.get("gpu_s") or 0.0
        stage.usd += price(entry)
        if entry.get("status") == "error":
            stage.errors += 1

    return dict(stages)


def markdown_table(stages: dict[str, StageCost]) -> str:
    rows = [
        "| Stage | Calls | Errors | Cache hits | Mean latency (s) | GPU minutes | List-price equivalent (USD) |",
        "|---|---|---|---|---|---|---|",
    ]
    total = StageCost()
    for name in sorted(stages):
        stage = stages[name]
        total.add(stage)
        rows.append(
            f"| {name} | {stage.calls} | {stage.errors} | {stage.cache_hits} "
            f"| {stage.mean_latency_s:.2f} | {stage.gpu_s / 60:.1f} | {stage.usd:.4f} |"
        )
    rows.append(
        f"| **Total** | {total.calls} | {total.errors} | {total.cache_hits} "
        f"| | {total.gpu_s / 60:.1f} | {total.usd:.4f} |"
    )
    return "\n".join(rows)


def write_into(document: Path, table: str) -> None:
    """Replace the table between the cost markers in COSTS.md."""
    text = document.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(START) + ".*?" + re.escape(END), re.DOTALL)
    if not pattern.search(text):
        raise ValueError(f"{document.name} has no {START} ... {END} block")

    block = f"{START}\n{table}\n{END}"
    document.write_text(pattern.sub(lambda _: block, text), encoding="utf-8")
