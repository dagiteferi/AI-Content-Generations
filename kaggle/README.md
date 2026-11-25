# GPU notebooks

Video (Wan 2.2) and music (ACE-Step) need a GPU, so they run on Kaggle (T4 x2, about 30 h a week) and are handed off through files.

## Round trip
1. Locally: `uv run heritage gpu export shots` (or `music`). This writes `kaggle/bundles/shots.zip` with `jobs.json`, the keyframes and the runner scripts.
2. On Kaggle: **Datasets → New dataset**, upload the zip.
3. New notebook: Accelerator **GPU T4 x2**, Internet **on**, **Add input** → your dataset.
4. Run:
   ```
   !pip install -q -U diffusers transformers accelerate ftfy imageio imageio-ffmpeg
   !python /kaggle/input/<dataset>/wan_shots.py
   !cd /kaggle/working && zip -qr out.zip out
   ```
   Each clip is saved as soon as it is done. If the session dies, run the cell again and finished jobs are skipped.
5. Download `out.zip` from the notebook's Output panel.
6. Locally: `uv run heritage gpu import ~/Downloads/out.zip`, then `uv run heritage run --stage shots`.

Import only accepts files that the current `storyboard.json` still expects. Outputs from an older storyboard are reported as stale and ignored. Each job's GPU seconds go into `runs.jsonl`.

## Music (ACE-Step 1.5)
Same round trip with `uv run heritage gpu export music`. ACE-Step needs its own environment (Python 3.11-3.12, installed with `uv sync`), so run the script through it:
```
!git clone https://github.com/ACE-Step/ACE-Step-1.5.git /kaggle/working/ACE-Step-1.5
!cd /kaggle/working/ACE-Step-1.5 && pip install -q uv && uv sync
!cd /kaggle/working/ACE-Step-1.5 && uv run python /kaggle/input/<dataset>/acestep_music.py /kaggle/input/<dataset> /kaggle/working/out
!cd /kaggle/working && zip -qr out.zip out
```
- Uses the 2B turbo model (`acestep-v15-turbo`, 8 steps, shift 3.0), the safer size for a 16 GB T4.
- The planner LM runs on the `pt` backend by default; set `ACESTEP_LM_BACKEND=vllm` to try the faster one.
- Not yet confirmed on a real Kaggle run: whether checkpoints download on the first API call, and the dtype on a T4. Note what you find in FAILURES.md.

## Tips
- Draft at `480p` (640x640). Switch chosen shots to `720p` (960x960) in the storyboard for the final render.
- Square clips keep the centred subject usable for both 9:16 and 16:9 crops.
- On a T4 there is no bf16, so the script falls back to float16. If you see black or NaN frames, note it in FAILURES.md and try fewer frames.
