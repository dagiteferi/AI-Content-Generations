"""ACE-Step 1.5 score candidates for every job in jobs.json.

Kaggle: GPU T4, internet on. Install ACE-Step 1.5 as its README describes (uv sync in the
cloned repo), then run this script with that environment's Python:
    !git clone https://github.com/ACE-Step/ACE-Step-1.5.git /kaggle/working/ACE-Step-1.5
    !cd /kaggle/working/ACE-Step-1.5 && pip install -q uv && uv sync
    !cd /kaggle/working/ACE-Step-1.5 && uv run python /kaggle/input/<bundle>/acestep_music.py \
        /kaggle/input/<bundle> /kaggle/working/out

API from docs/en/INFERENCE.md (Python API, "Quick Start"). Each job gives: caption, lyrics
("[instrumental]" for a score), duration_s, bpm, key, seed. Every parameter comes from the
job, so the storyboard stays the single source of truth.
"""

import os
import shutil
import tempfile
from pathlib import Path

from runner import Job, run_jobs

PROJECT_ROOT = Path(os.environ.get("ACESTEP_ROOT", "/kaggle/working/ACE-Step-1.5"))
DIT_CONFIG = os.environ.get("ACESTEP_DIT", "acestep-v15-turbo")  # 2B turbo: the safe choice on a 16 GB T4
LM_MODEL = os.environ.get("ACESTEP_LM", "acestep-5Hz-lm-0.6B")
LM_BACKEND = os.environ.get("ACESTEP_LM_BACKEND", "pt")  # "vllm" is faster but heavier to install on Kaggle
TURBO_STEPS = 8  # recommended for turbo (1-20)
TURBO_SHIFT = 3.0  # the docs say turbo wants shift=3.0; it is not set automatically


def load_handlers():
    from acestep.handler import AceStepHandler
    from acestep.llm_inference import LLMHandler

    dit_handler = AceStepHandler()
    dit_handler.initialize_service(project_root=str(PROJECT_ROOT), config_path=DIT_CONFIG, device="cuda")
    llm_handler = LLMHandler()
    llm_handler.initialize(
        checkpoint_dir=str(PROJECT_ROOT / "checkpoints"),
        lm_model_path=LM_MODEL,
        backend=LM_BACKEND,
        device="cuda",
    )
    return dit_handler, llm_handler


DIT, LLM = load_handlers()


def generate(job: Job, bundle: Path, output: Path) -> None:
    from acestep.inference import GenerationConfig, GenerationParams, generate_music

    instrumental = job["lyrics"].strip().lower() in ("", "[instrumental]")
    params = GenerationParams(
        caption=job["caption"],
        lyrics="[Instrumental]" if instrumental else job["lyrics"],
        instrumental=instrumental,
        duration=float(job["duration_s"]),
        bpm=job.get("bpm"),
        keyscale=job.get("key") or "",
        seed=int(job["seed"]),
        inference_steps=TURBO_STEPS,
        shift=TURBO_SHIFT,
    )
    config = GenerationConfig(batch_size=1, use_random_seed=False, seeds=[int(job["seed"])], audio_format="wav")

    with tempfile.TemporaryDirectory() as save_dir:
        result = generate_music(DIT, LLM, params, config, save_dir=save_dir)
        if not result.success:
            raise RuntimeError(f"ACE-Step failed: {result.error}")
        # The docs do not fix the file name, so take the path the result reports.
        shutil.move(result.audios[0]["path"], output)


if __name__ == "__main__":
    run_jobs(generate)
