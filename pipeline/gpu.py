"""File-based hand-off to GPU notebooks (Kaggle/Colab).

`export_bundle` writes jobs.json, the input images and the runner scripts into one zip.
The notebook writes clips or tracks plus results.jsonl; `import_results` copies back
only files the current storyboard still expects and logs each job to runs.jsonl.
"""

import json
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from pipeline.config import Settings
from pipeline.core.runlog import Call, RunLog
from pipeline.errors import StageError
from pipeline.models import Storyboard
from pipeline.prompts import NEGATIVE_MOTION
from pipeline.stages import music, shots
from pipeline.stages.keyframes import keyframe_path

Kind = Literal["shots", "music"]
RUNNERS = {"shots": "wan_shots.py", "music": "acestep_music.py"}
SHARED_FILES = ("runner.py",)


@dataclass
class ImportSummary:
    imported: list[str] = field(default_factory=list)
    already_present: list[str] = field(default_factory=list)
    stale: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)


def shot_jobs(settings: Settings, storyboard: Storyboard, include_done: bool = False) -> list[dict]:
    jobs = []
    for shot in storyboard.shots:
        clip = shots.clip_path(settings.outputs_dir, shot, storyboard)
        keyframe = keyframe_path(settings.outputs_dir, shot, storyboard)
        if (clip.exists() and not include_done) or not keyframe.exists():
            continue
        size = shots.SQUARE_SIZE[shot.motion.resolution]
        jobs.append(
            {
                "id": shot.id,
                "model": shot.motion.model,
                "image": f"images/{keyframe.name}",
                "prompt": shot.motion.prompt,
                "negative_prompt": NEGATIVE_MOTION,
                "seed": shot.motion.seed,
                "width": size,
                "height": size,
                "frames": shot.motion.frames,
                "fps": shots.FPS,
                "steps": shots.WAN_STEPS,
                "guidance": shots.WAN_GUIDANCE,
                "output": clip.name,
            }
        )
    return jobs


def music_jobs(settings: Settings, storyboard: Storyboard, include_done: bool = False) -> list[dict]:
    score = storyboard.music
    jobs = []
    for cue in score.cues:
        for seed in score.seeds:
            path = music.candidate_path(settings.outputs_dir, cue, score, seed)
            if path.exists() and not include_done:
                continue
            jobs.append(
                {
                    "id": f"{cue.id}#{seed}",
                    "model": score.model,
                    "caption": cue.caption,
                    "lyrics": "[instrumental]" if cue.instrumental else "",
                    "duration_s": cue.end_s - cue.start_s,
                    "bpm": cue.bpm,
                    "key": cue.key,
                    "seed": seed,
                    "output": path.name,
                }
            )
    return jobs


def expected_outputs(settings: Settings, storyboard: Storyboard, kind: Kind) -> dict[str, dict]:
    jobs = shot_jobs if kind == "shots" else music_jobs
    return {job["output"]: job for job in jobs(settings, storyboard, include_done=True)}


def missing_keyframes(settings: Settings, storyboard: Storyboard) -> list[str]:
    return [
        shot.id
        for shot in storyboard.shots
        if not keyframe_path(settings.outputs_dir, shot, storyboard).exists()
    ]


def export_bundle(settings: Settings, storyboard: Storyboard, kind: Kind, include_done: bool = False) -> tuple[Path, int]:
    if kind == "shots" and (missing := missing_keyframes(settings, storyboard)):
        raise StageError(f"Keyframes missing for {', '.join(missing)}. Run: heritage run --stage keyframes")
    jobs = (shot_jobs if kind == "shots" else music_jobs)(settings, storyboard, include_done)
    if not jobs:
        raise StageError(f"No {kind} jobs to export: every output is already present")

    kaggle_dir = settings.root / "kaggle"
    bundle_dir = kaggle_dir / "bundles" / kind
    shutil.rmtree(bundle_dir, ignore_errors=True)
    (bundle_dir / "images").mkdir(parents=True)

    for job in jobs:
        if "image" in job:
            shutil.copy2(settings.outputs_dir / "keyframes" / Path(job["image"]).name, bundle_dir / job["image"])
    for script in (RUNNERS[kind], *SHARED_FILES):
        shutil.copy2(kaggle_dir / script, bundle_dir / script)
    (bundle_dir / "jobs.json").write_text(json.dumps({"kind": kind, "jobs": jobs}, indent=2, ensure_ascii=False), encoding="utf-8")

    archive = shutil.make_archive(str(bundle_dir), "zip", root_dir=bundle_dir)
    return Path(archive), len(jobs)


def _results_dir(source: Path, scratch: Path) -> Path:
    if source.is_file() and source.suffix == ".zip":
        with zipfile.ZipFile(source) as archive:
            archive.extractall(scratch)
        source = scratch
    matches = list(source.rglob("results.jsonl"))
    if not matches:
        raise StageError(f"No results.jsonl found in {source}")
    return matches[0].parent


def _latest_results(path: Path) -> list[dict]:
    latest: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            result = json.loads(line)
            latest[result["output"]] = result
    return list(latest.values())


def import_results(settings: Settings, storyboard: Storyboard, source: Path, log: RunLog) -> ImportSummary:
    summary = ImportSummary()
    with tempfile.TemporaryDirectory() as scratch:
        results_dir = _results_dir(source, Path(scratch))
        for result in _latest_results(results_dir / "results.jsonl"):
            kind: Kind = result["kind"]
            expected = expected_outputs(settings, storyboard, kind)
            job = expected.get(result["output"])
            if job is None:
                summary.stale.append(result["output"])
                continue

            call = Call(
                stage=kind,
                provider="kaggle",
                model=job["model"],
                shot=job["id"],
                params={k: job[k] for k in ("steps", "guidance", "width", "frames") if k in job},
                seed=job["seed"],
            )
            if result["status"] != "ok":
                log.record(call, status="error", latency_s=result.get("seconds", 0.0), error=result.get("error"))
                summary.failed.append(job["id"])
                continue

            destination = settings.outputs_dir / kind / result["output"]
            if destination.exists():
                summary.already_present.append(job["id"])
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(results_dir / result["output"], destination)
            log.record(
                call,
                status="ok",
                latency_s=result.get("seconds", 0.0),
                gpu_s=result.get("seconds"),
                output=destination,
            )
            summary.imported.append(job["id"])
    return summary
