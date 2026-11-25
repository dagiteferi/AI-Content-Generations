"""Summarise runs.jsonl per stage: calls, cache hits, latency, GPU minutes, list-price equivalent."""

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

# List-price assumptions (USD), used only to estimate what the free run would cost on paid tiers.
# Check each one when you fill in COSTS.md; the table there names the source of every figure.
GPU_USD_PER_HOUR = 0.35  # one NVIDIA T4, on-demand cloud list price
USD_PER_CALL = {
    "gemini": 0.002,  # one short Flash / Flash TTS request
    "cloudflare": 0.0011,  # one FLUX.1 schnell image
}
MARKER_START = "<!-- costs:start -->"
MARKER_END = "<!-- costs:end -->"


@dataclass
class StageCost:
    calls: int = 0
    cache_hits: int = 0
    errors: int = 0
    fallbacks: int = 0
    latencies: list[float] = field(default_factory=list)
    gpu_s: float = 0.0
    usd: float = 0.0

    @property
    def mean_latency_s(self) -> float:
        return sum(self.latencies) / len(self.latencies) if self.latencies else 0.0


def entry_cost(entry: dict) -> float:
    if entry.get("cost_usd_list") is not None:
        return float(entry["cost_usd_list"])
    if entry.get("gpu_s"):
        return entry["gpu_s"] / 3600 * GPU_USD_PER_HOUR
    return USD_PER_CALL.get(entry.get("provider", ""), 0.0)


def summarise(runs: Path) -> dict[str, StageCost]:
    stages: dict[str, StageCost] = defaultdict(StageCost)
    if not runs.exists():
        return {}
    for line in runs.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        cost = stages[entry["stage"]]
        if entry.get("cache") == "hit":
            cost.cache_hits += 1
            continue
        cost.calls += 1
        cost.latencies.append(entry.get("latency_s") or 0.0)
        cost.gpu_s += entry.get("gpu_s") or 0.0
        if entry.get("status") == "error":
            cost.errors += 1
        if entry.get("status") == "fallback":
            cost.fallbacks += 1
        cost.usd += entry_cost(entry)
    return dict(stages)


def markdown_table(stages: dict[str, StageCost]) -> str:
    rows = [
        "| Stage | Calls | Errors | Cache hits | Mean latency (s) | GPU minutes | List-price equivalent (USD) |",
        "|---|---|---|---|---|---|---|",
    ]
    total = StageCost()
    for name in sorted(stages):
        cost = stages[name]
        rows.append(
            f"| {name} | {cost.calls} | {cost.errors} | {cost.cache_hits} | {cost.mean_latency_s:.2f} "
            f"| {cost.gpu_s / 60:.1f} | {cost.usd:.4f} |"
        )
        total.calls += cost.calls
        total.errors += cost.errors
        total.cache_hits += cost.cache_hits
        total.gpu_s += cost.gpu_s
        total.usd += cost.usd
    rows.append(
        f"| **Total** | {total.calls} | {total.errors} | {total.cache_hits} | | "
        f"{total.gpu_s / 60:.1f} | {total.usd:.4f} |"
    )
    return "\n".join(rows)


def write_into(document: Path, table: str) -> None:
    """Replace the generated block between the cost markers in COSTS.md."""
    text = document.read_text(encoding="utf-8")
    block = f"{MARKER_START}\n{table}\n{MARKER_END}"
    pattern = re.compile(re.escape(MARKER_START) + r".*?" + re.escape(MARKER_END), re.DOTALL)
    if not pattern.search(text):
        raise ValueError(f"{document.name} has no {MARKER_START} ... {MARKER_END} block")
    document.write_text(pattern.sub(lambda _: block, text), encoding="utf-8")
