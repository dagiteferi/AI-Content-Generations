"""ACE-Step 1.5 score candidates for every job in jobs.json.

Kaggle: GPU T4, internet on. Install ACE-Step 1.5 as its README describes, then:
    !python /kaggle/input/<bundle>/acestep_music.py

Each job gives: caption, lyrics ("[instrumental]" for a score), duration_s, bpm, key, seed.
The output must be a WAV file at the path passed to `generate`.
"""

from pathlib import Path

from runner import Job, run_jobs


def generate(job: Job, bundle: Path, output: Path) -> None:
    # Wire this to the ACE-Step 1.5 inference API once it is confirmed against the
    # official README (https://github.com/ACE-Step/ACE-Step-1.5). Keep every parameter
    # coming from `job` so the storyboard stays the single source of truth.
    raise NotImplementedError("ACE-Step 1.5 call not wired yet: see the README of ACE-Step-1.5")


if __name__ == "__main__":
    run_jobs(generate)
