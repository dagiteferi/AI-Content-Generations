"""Shared job loop for GPU notebooks: resumable, one results.jsonl line per job."""

import json
import sys
import time
import traceback
from collections.abc import Callable
from pathlib import Path

Job = dict
Generate = Callable[[Job, Path, Path], None]


def paths_from_argv() -> tuple[Path, Path]:
    bundle = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("/kaggle/working/out")
    out_dir.mkdir(parents=True, exist_ok=True)
    return bundle, out_dir


def run_jobs(generate: Generate) -> None:
    bundle, out_dir = paths_from_argv()
    spec = json.loads((bundle / "jobs.json").read_text(encoding="utf-8"))
    results = out_dir / "results.jsonl"
    jobs = spec["jobs"]

    for number, job in enumerate(jobs, start=1):
        output = out_dir / job["output"]
        if output.exists():
            print(f"[{number}/{len(jobs)}] {job['id']} already done")
            continue

        print(f"[{number}/{len(jobs)}] {job['id']} ...", flush=True)
        started = time.perf_counter()
        record = {"kind": spec["kind"], "id": job["id"], "output": job["output"]}
        try:
            generate(job, bundle, output)
            record |= {"status": "ok", "error": None}
        except Exception as error:
            traceback.print_exc()
            output.unlink(missing_ok=True)
            record |= {"status": "error", "error": f"{type(error).__name__}: {error}"[:500]}
        record["seconds"] = round(time.perf_counter() - started, 1)

        with results.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")
        print(f"    {record['status']} in {record['seconds']}s", flush=True)
