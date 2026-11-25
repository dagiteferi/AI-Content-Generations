"""Generate ACE-Step 1.5 score candidates for every job in jobs.json (see kaggle/README.md)."""

import os
import shutil
import tempfile
from pathlib import Path

from acestep.handler import AceStepHandler
from acestep.inference import GenerationConfig, GenerationParams, generate_music
from acestep.llm_inference import LLMHandler

from runner import Job, run_jobs

ACESTEP_ROOT = Path(os.environ.get("ACESTEP_ROOT", "/kaggle/working/ACE-Step-1.5"))
DIT_MODEL = "acestep-v15-turbo"
LM_MODEL = "acestep-5Hz-lm-0.6B"
LM_BACKEND = os.environ.get("ACESTEP_LM_BACKEND", "pt")
STEPS = 8
SHIFT = 3.0  # turbo needs this set by hand


def load_models() -> tuple[AceStepHandler, LLMHandler]:
    dit = AceStepHandler()
    dit.initialize_service(project_root=str(ACESTEP_ROOT), config_path=DIT_MODEL, device="cuda")

    planner = LLMHandler()
    planner.initialize(
        checkpoint_dir=str(ACESTEP_ROOT / "checkpoints"),
        lm_model_path=LM_MODEL,
        backend=LM_BACKEND,
        device="cuda",
    )
    return dit, planner


DIT, PLANNER = load_models()


def generate(job: Job, bundle: Path, output: Path) -> None:
    instrumental = job["lyrics"].strip().lower() in ("", "[instrumental]")
    seed = int(job["seed"])

    params = GenerationParams(
        caption=job["caption"],
        lyrics="[Instrumental]" if instrumental else job["lyrics"],
        instrumental=instrumental,
        duration=float(job["duration_s"]),
        bpm=job.get("bpm"),
        keyscale=job.get("key") or "",
        seed=seed,
        inference_steps=STEPS,
        shift=SHIFT,
    )
    config = GenerationConfig(batch_size=1, use_random_seed=False, seeds=[seed], audio_format="wav")

    with tempfile.TemporaryDirectory() as save_dir:
        result = generate_music(DIT, PLANNER, params, config, save_dir=save_dir)
        if not result.success:
            raise RuntimeError(f"ACE-Step failed: {result.error}")
        shutil.move(result.audios[0]["path"], output)


if __name__ == "__main__":
    run_jobs(generate)
