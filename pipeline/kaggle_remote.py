"""Run the GPU hand-off on Kaggle from the terminal: upload jobs, start the notebook, fetch results.

Uses the official `kaggle` CLI with KAGGLE_API_TOKEN (or KAGGLE_USERNAME + KAGGLE_KEY) from .env.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from pipeline.config import Settings
from pipeline.core.runlog import RunLog
from pipeline.errors import StageError
from pipeline.gpu import ImportSummary, Kind, export_bundle, import_results
from pipeline.models import Storyboard

MACHINE = "NvidiaTeslaT4"

# What each notebook installs before running its job script.
SETUP = {
    "shots": [
        ["pip", "install", "-q", "-U", "diffusers>=0.43", "transformers", "accelerate", "ftfy", "imageio", "imageio-ffmpeg"],
    ],
    "music": [
        ["git", "clone", "--depth", "1", "https://github.com/ACE-Step/ACE-Step-1.5.git", "/kaggle/working/ACE-Step-1.5"],
        ["pip", "install", "-q", "uv"],
        ["uv", "sync", "--directory", "/kaggle/working/ACE-Step-1.5"],
    ],
}
SCRIPT = {"shots": "wan_shots.py", "music": "acestep_music.py"}

KERNEL_RUNNER = '''\
import glob, os, subprocess, sys, zipfile

def find_bundle():
    jobs = glob.glob("/kaggle/input/**/jobs.json", recursive=True)
    if jobs:
        return os.path.dirname(jobs[0])
    for archive in glob.glob("/kaggle/input/**/*.zip", recursive=True):
        zipfile.ZipFile(archive).extractall("/kaggle/working/bundle")
        return "/kaggle/working/bundle"
    sys.exit("no jobs.json or bundle zip found under /kaggle/input")

bundle = find_bundle()
print("bundle:", bundle, flush=True)
for command in SETUP:
    if command[0] == "pip":
        command = [sys.executable, "-m", *command]
    print("$", " ".join(command), flush=True)
    subprocess.run(command, check=True)

script = os.path.join(bundle, SCRIPT)
if KIND == "music":
    command = ["uv", "run", "--directory", "/kaggle/working/ACE-Step-1.5", "python", script, bundle, "/kaggle/working/out"]
else:
    command = [sys.executable, script, bundle, "/kaggle/working/out"]
print("$", " ".join(command), flush=True)
subprocess.run(command, check=True)
'''


def _env(settings: Settings) -> dict[str, str]:
    env = dict(os.environ)
    if settings.kaggle_api_token:
        env["KAGGLE_API_TOKEN"] = settings.secret("kaggle_api_token")
    elif settings.kaggle_username and settings.kaggle_key:
        env["KAGGLE_USERNAME"] = settings.kaggle_username
        env["KAGGLE_KEY"] = settings.secret("kaggle_key")
    else:
        raise StageError("Set KAGGLE_API_TOKEN (or KAGGLE_USERNAME and KAGGLE_KEY) in .env")
    return env


def kaggle(settings: Settings, *args: str, check: bool = True) -> str:
    executable = shutil.which("kaggle") or str(Path(sys.executable).parent / "kaggle")
    result = subprocess.run([executable, *args], capture_output=True, text=True, env=_env(settings))
    output = (result.stdout + result.stderr).strip()
    if check and result.returncode != 0:
        raise StageError(f"kaggle {' '.join(args[:2])} failed: {output[-600:]}")
    return output


def username(settings: Settings) -> str:
    match = re.search(r"username:\s*(\S+)", kaggle(settings, "config", "view"))
    if not match:
        raise StageError("Could not read the Kaggle username from `kaggle config view`")
    return match.group(1)


def ids(settings: Settings, kind: Kind) -> tuple[str, str]:
    user = username(settings)
    return f"{user}/heritage-{kind}-jobs", f"{user}/heritage-{kind}-run"


def push(settings: Settings, storyboard: Storyboard, kind: Kind) -> tuple[str, int]:
    """Upload the job bundle as a dataset and start the GPU notebook. Returns the kernel id."""
    archive, count = export_bundle(settings, storyboard, kind)
    dataset_id, kernel_id = ids(settings, kind)

    with tempfile.TemporaryDirectory() as scratch:
        data_dir = Path(scratch) / "dataset"
        data_dir.mkdir()
        shutil.copy2(archive, data_dir / archive.name)
        meta = {"title": f"heritage-{kind}-jobs", "id": dataset_id, "licenses": [{"name": "CC0-1.0"}]}
        (data_dir / "dataset-metadata.json").write_text(json.dumps(meta))

        exists = "ready" in kaggle(settings, "datasets", "status", dataset_id, check=False).lower()
        if exists:
            kaggle(settings, "datasets", "version", "-p", str(data_dir), "-m", f"{count} {kind} jobs")
        else:
            kaggle(settings, "datasets", "create", "-p", str(data_dir))

        kernel_dir = Path(scratch) / "kernel"
        kernel_dir.mkdir()
        runner = f"KIND = {kind!r}\nSCRIPT = {SCRIPT[kind]!r}\nSETUP = {SETUP[kind]!r}\n\n{KERNEL_RUNNER}"
        (kernel_dir / "run.py").write_text(runner)
        meta = {
            "id": kernel_id,
            "title": f"heritage-{kind}-run",
            "code_file": "run.py",
            "language": "python",
            "kernel_type": "script",
            "is_private": True,
            "enable_gpu": True,
            "enable_internet": True,
            "machine_shape": MACHINE,
            "dataset_sources": [dataset_id],
        }
        (kernel_dir / "kernel-metadata.json").write_text(json.dumps(meta, indent=2))
        _wait_for_dataset(settings, dataset_id)
        kaggle(settings, "kernels", "push", "-p", str(kernel_dir))
    return kernel_id, count


def _wait_for_dataset(settings: Settings, dataset_id: str, tries: int = 30) -> None:
    for _ in range(tries):
        if "ready" in kaggle(settings, "datasets", "status", dataset_id, check=False).lower():
            return
        time.sleep(10)
    raise StageError(f"Dataset {dataset_id} was not ready after {tries * 10}s")


def status(settings: Settings, kind: Kind) -> str:
    _, kernel_id = ids(settings, kind)
    output = kaggle(settings, "kernels", "status", kernel_id, check=False)
    match = re.search(r'status "?([A-Za-z.]+)"?', output)
    return (match.group(1) if match else output).split(".")[-1].lower()


def pull(settings: Settings, storyboard: Storyboard, kind: Kind, log: RunLog) -> ImportSummary:
    """Download the notebook's output and import every finished clip or track."""
    _, kernel_id = ids(settings, kind)
    with tempfile.TemporaryDirectory() as scratch:
        kaggle(settings, "kernels", "output", kernel_id, "-p", scratch)
        log_files = list(Path(scratch).glob("*.log"))
        if log_files:
            shutil.copy2(log_files[0], settings.root / "kaggle" / f"last-{kind}-run.log")
        return import_results(settings, storyboard, Path(scratch), log)
