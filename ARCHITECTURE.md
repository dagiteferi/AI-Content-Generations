# Architecture

How the Heritage Short pipeline turns `storyboard.json` into a finished film: its stages, the contracts between them, caching and failure handling. The requirements it implements are listed in [REQUIREMENTS.md](REQUIREMENTS.md).

## 1. Overview

The pipeline is a **Python CLI**. Its design rests on four decisions:

1. **One contract.** `storyboard.json` describes the whole film. Prompts, seeds and narration live there, not in code.
2. **Independent stages.** Each stage reads the storyboard plus files in `outputs/`, and writes files to `outputs/`. Stages never call each other.
3. **Content-addressed cache.** Each output is keyed by a hash of everything that produced it, so only what changed is regenerated.
4. **Providers behind interfaces.** Every model is an adapter, so models can be swapped and fallbacks are cheap.

```
                         storyboard.json  ──validate──►  schema/storyboard.schema.json
                                │
        ┌───────────────┬───────┴───────┬────────────────┬────────────────┐
        ▼               ▼               ▼                ▼                │
   [narration]     [reference]       [music]        (shot timing)         │
   Gemini TTS      FLUX ref sheet    ACE-Step ×3          │               │
        │               │               │                 │               │
        │               ▼               │                 │               │
        │          [keyframes]          │                 │               │
        │          FLUX + style block   │                 │               │
        │               │               │                 │               │
        │               ▼               │                 │               │
        │           [shots]             │                 │               │
        │      Wan 2.2 on Kaggle        │                 │               │
        │      └─fallback: Ken Burns    │                 │               │
        │               │               │                 │               │
        ▼               ▼               ▼                 ▼               ▼
   ┌──────────────────────────────── [assemble] ─────────────────────────────┐
   │ FFmpeg: concat → duck music → subtitles → end card → loudnorm → 2 ratios │
   └──────────────────────────────────────────────────────────────────────────┘
                                │
                outputs/final/film_9x16.mp4 · film_16x9.mp4

   cross-cutting: config (.env) · cache · retry/fallback · runs.jsonl logger
```

The **radio cut** is assembly run early with narration only and a black picture. It comes from the same code path.

## 2. Repository layout

```
heritage-short/
├── Makefile                    # make film | make radio | make smoke | make test
├── pyproject.toml / uv.lock    # pinned dependencies
├── .env.example                # GEMINI_API_KEY, CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN, KAGGLE_*
├── storyboard.json             # THE contract
├── schema/
│   └── storyboard.schema.json  # generated from pipeline/models.py
├── pipeline/
│   ├── cli.py                  # typer: validate, schema, smoke, draft, run, approve-reference, gpu
│   ├── models.py               # Pydantic contract: Storyboard, Shot, Voice, MusicCue, Character
│   ├── storyboard.py           # load/save, schema export, consent gate
│   ├── config.py               # settings from env (pydantic-settings)
│   ├── context.py              # StageContext: storyboard, settings, log, shot filter, flags
│   ├── orchestrator.py         # runs stages in dependency order
│   ├── smoke.py                # one call per provider, latency logged
│   ├── prompts.py              # prompt composition: shot + characters + style block
│   ├── gpu.py                  # Kaggle hand-off: export job bundles, import results
│   ├── errors.py               # expected failures with actionable messages
│   ├── core/
│   │   ├── cache.py            # cache keys, file digests, atomic writes
│   │   ├── runlog.py           # appends to runs.jsonl
│   │   ├── retry.py            # logged attempts + backoff on transient errors
│   │   └── media.py            # ffmpeg/ffprobe helpers
│   ├── providers/              # one adapter per external model/tool
│   │   ├── base.py             # Protocols: TextModel, SpeechModel, ImageModel
│   │   ├── gemini.py           # text + TTS
│   │   ├── cloudflare.py       # FLUX on Workers AI
│   │   ├── factory.py          # model id -> provider
│   │   ├── kenburns.py         # FFmpeg zoompan fallback that follows the camera note
│   │   └── kaggle.py           # account check
│   └── stages/
│       ├── script.py           # brief -> storyboard (Gemini, validated with repair loop)
│       ├── narration.py        # Gemini TTS per shot
│       ├── reference.py        # character reference candidates (one per seed)
│       ├── keyframes.py        # FLUX still per shot
│       ├── shots.py            # imported Wan clip, else Ken Burns fallback
│       ├── music.py            # ACE-Step candidates + the storyboard's choice
│       └── radio.py            # narration + placeholder music on black
│                               # phase 3: assemble
├── kaggle/                     # GPU side: runner.py (resumable job loop), wan_shots.py, acestep_music.py
├── references/                 # approved reference sheet / golden reference images
├── outputs/                    # generated media (large files git-ignored, manifests kept)
│   ├── narration/ reference/ keyframes/ shots/ music/ radio_cut/ final/
├── runs.jsonl                  # one line per model call
├── tests/
└── README.md DESIGN.md ARCHITECTURE.md REQUIREMENTS.md
    EXPERIMENTS.md FAILURES.md COSTS.md ETHICS.md
```

## 3. The contract: `storyboard.json`

The source of truth is the Pydantic models in `pipeline/models.py`. `heritage schema` exports them to `schema/storyboard.schema.json`. The shape is:

```jsonc
{
  "version": 1,
  "title": "…",
  "language": "am",                     // narration language (BCP-47)
  "subtitle_language": "en",
  "target_duration_s": 75,              // must be 60–90
  "style_block": "warm hand-painted look, soft golden-hour light, muted earth palette",
  "characters": [
    { "id": "grandmother", "description": "…", "reference_image": "references/grandmother.png",
      "real_person": true, "consent_ref": "ETHICS.md#grandmother" }
  ],
  "voice": { "provider": "gemini-tts", "voice_name": "…", "style": "calm, warm, unhurried" },
  "music": {
    "cues": [ { "id": "main", "start_s": 0, "end_s": 75, "caption": "…", "bpm": 72, "key": "D minor", "instrumental": true } ],
    "candidates": 3,
    "chosen": null,                     // set after listening, e.g. "main#seed=1234"
    "choice_reason": null
  },
  "shots": [
    {
      "id": "s01",
      "duration_s": 7.0,
      "purpose": "Establish the market in Dessie at dawn",   // why this shot exists
      "shot_size": "extreme-wide",
      "camera": "slow push-in",
      "characters": [],
      "keyframe": { "prompt": "…", "seed": 42, "model": "flux-1-schnell" },
      "motion":   { "prompt": "the camera pushes in gently, mist drifts", "seed": 7, "model": "wan2.2-ti2v-5b", "resolution": "480p" },
      "narration": { "text": "…source language…", "subtitle": "…English…" },
      "fallback": "kenburns"           // kenburns | still | none
    }
  ],
  "end_card": { "text": "Made with AI …", "duration_s": 3 }
}
```

Validation rules beyond the types:
- 8 ≤ shots ≤ 12.
- The sum of shot durations plus the end card is between 60 and 90 s.
- Shot ids are unique.
- Every character a shot references exists.
- Every `real_person` has a `consent_ref` (the consent gate).

## 4. Stage contracts

| Stage | Reads | Writes | Cache key includes | Provider (fallback) |
|---|---|---|---|---|
| `narration` | `shots[].narration`, `voice` | `outputs/narration/<shot>.<key>.wav` + duration | text, voice, style, model | Gemini TTS |
| `reference` | `characters`, `style_block` | `outputs/reference/<char>.<key>.png` | description, style block, seed, model | FLUX (Cloudflare) |
| `keyframes` | `shots[].keyframe`, style block, characters, approved reference | `outputs/keyframes/<shot>.<key>.png` | prompt + style block + character text, seed, model, hash of reference image | FLUX (retry → different seed) |
| `shots` | keyframe file, `shots[].motion` | `outputs/shots/<shot>.<key>.mp4` | keyframe hash, motion prompt, seed, model, resolution | Wan 2.2 (→ Ken Burns) |
| `music` | `music.cues` | `outputs/music/<cue>.seed<N>.<key>.wav` | caption, bpm, key, duration, seed, model | ACE-Step |
| `assemble` | all of the above, `end_card` | `outputs/final/film_9x16.mp4`, `film_16x9.mp4`, `subtitles.srt` | hashes of every input file + assembly params | FFmpeg (deterministic) |
| `radio` | narration, placeholder music | `outputs/radio_cut/radio.mp4` | narration hashes | FFmpeg |

Dependency order: `narration, reference, music` → `keyframes` → `shots` → `assemble`.
With `--shot s03`, the orchestrator limits every stage to that shot, and assembly re-runs because one of its input hashes changed.

## 5. Caching

```
key = sha256(canonical_json({
        "stage": ..., "model": ..., "params": {...}, "seed": ...,
        "prompt": <final prompt after style block added>,
        "inputs": [sha256(file) for each upstream file]
      }))[:12]
```

- The output file name contains the key. A file with that key already existing means a cache hit, and no call is made.
- Upstream changes flow down automatically. A new keyframe prompt gives a new keyframe hash, which gives a new shot key, which gives a new assembly key. Narration, music and the other shots stay as cache hits.
- Writes are atomic: the output goes to `*.tmp` first and is renamed only after it passes validation (non-empty, ffprobe-readable).
- `--force` skips the lookup. `--dry-run` prints hit or miss for each artefact.

This is exactly what the walkthrough demo shows: edit one prompt and only one keyframe, one clip and the final assembly regenerate.

## 6. Failure handling

```
attempt 1 ──fail(transient)──► backoff ──► attempt 2 ──► … attempt 3
     │                                                       │
     ok                                               still failing
     ▼                                                       ▼
   cache                                  shot.fallback (kenburns / still)
                                          logged status="fallback"; run continues
```

| Failure | Handling |
|---|---|
| Timeout, 429, 5xx | Exponential backoff with jitter (tenacity), at most 3 attempts |
| Daily quota exhausted (Cloudflare) | Stop the stage cleanly. Cached work is kept, and a re-run tomorrow resumes |
| Kaggle session timeout or GPU OOM | The notebook saves each clip as it finishes. Missing clips fall back to Ken Burns. Next step is to draft at 480p or use fewer frames |
| Bad output (empty, unreadable, wrong length) | Treated as a failed attempt |
| Narration longer than the shot | Warning with the overrun in seconds. Assembly extends the shot (hold or Ken Burns) rather than cutting the voice |
| Invalid storyboard or missing consent | Hard stop before any call |

Every failure is logged in `runs.jsonl`. The ones worth keeping go into `FAILURES.md`.

## 7. Logging: `runs.jsonl`

One JSON object per model call (cache hits are logged too, with `cache: "hit"`):

```json
{"ts":"2026-11-24T14:02:11Z","run_id":"r-20261124-1402","stage":"keyframes","shot":"s03",
 "provider":"cloudflare","model":"@cf/black-forest-labs/flux-1-schnell",
 "params":{"steps":4,"width":768,"height":1344},"seed":42,"cache":"miss","attempt":1,
 "latency_s":2.31,"gpu_s":null,"cost_usd_list":0.0011,"status":"ok","error":null,
 "output":"outputs/keyframes/s03.a1b2c3d4e5f6.png"}
```

`heritage report costs` aggregates this file into the tables in `COSTS.md`.

## 8. Where things run

| Component | Runs on | Why |
|---|---|---|
| CLI, orchestrator, FFmpeg assembly | Laptop | Deterministic, free, fast |
| Gemini text + TTS, FLUX | Hosted APIs (Gemini, Cloudflare) | Free tier, no GPU needed |
| Wan 2.2, ACE-Step | Kaggle (2×T4), Colab as backup | Needs a GPU. Jobs are batched |

### GPU hand-off

The hand-off is file-based, so the pipeline stays reproducible even though the GPU is remote and only available some of the time:

```
heritage gpu export shots ──► kaggle/bundles/shots.zip  (jobs.json + keyframes + runner scripts)
                                    │  upload as a Kaggle dataset
                                    ▼
                        wan_shots.py on T4 x2: one clip per job, saved immediately,
                        finished jobs skipped on re-run, results.jsonl line per job
                                    │  download out.zip
                                    ▼
heritage gpu import out.zip ──► outputs/shots/<shot>.<key>.mp4  + runs.jsonl (gpu_s)
```

- Each job's output name **is** its cache key, so an imported clip is a cache hit for exactly the storyboard that produced it.
- Import rejects outputs the current storyboard no longer expects (reported as *stale*), so an edited prompt can never pick up an old clip.
- Until a shot's clip arrives, the shots stage renders its fallback locally (`kenburns`, `still` or `none` per shot). The Ken Burns movement follows the shot's `camera` note (push-in, pull-back, pan, tilt), which keeps consecutive shots varied. A real clip always takes priority over the fallback.

### Frame format

Keyframes are square (FLUX.1 schnell's 1024x1024 default), and clips are square too: 640x640 for drafts, 960x960 for finals, which is about the pixel count of Wan's 1280x704. Prompts ask for a centred subject, so one clip can be cropped to both 9:16 and 16:9 in assembly. The cost is resolution: a 9:16 crop of a 960 square is 540x960, upscaled to 1080x1920.

### Character consistency

FLUX.1 schnell on Workers AI is text-to-image only, so consistency comes from the text. Every keyframe prompt gets the same character description and style block (`pipeline/prompts.py`), and the seeds are fixed. The approved reference (`references/<id>.jpg`) is the golden reference that keyframes are checked against. Conditioning on it directly with FLUX.2 klein's reference images is the planned next step.

## 9. Tech choices

| Concern | Choice | Reason |
|---|---|---|
| Language / packaging | Python 3.12, `uv` | Fast, lock file for reproducibility |
| CLI | `typer` | Typed, auto-generated help |
| Data models / schema | `pydantic` v2 | One source for validation and JSON Schema |
| Config | `pydantic-settings` + `.env` | Secrets stay out of the repo |
| Retries | `tenacity` | Standard backoff patterns |
| Gemini | `google-genai` SDK | Official client for text and TTS |
| Cloudflare | `httpx` REST | Simple, one endpoint |
| Media | FFmpeg / ffprobe via `subprocess` | Deterministic, covers every assembly need |
| Tests | `pytest` | Schema, cache keys, timing |

## 10. Extension points

- **A new model:** add a provider adapter and reference it by `model` in the storyboard.
- **A new language:** change `language` and `voice`. Nothing else changes.
- **A web or MCP interface:** a thin layer over `orchestrator.run()`. This is optional ceiling work.
