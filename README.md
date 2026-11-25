# Heritage Short

Turn a family story into a 60–90 second narrated short film, entirely in code.

You write the story once in `storyboard.json`. The pipeline turns it into keyframes, moving shots, narration, an original score and a finished edit, exported as a vertical (9:16) and a horizontal (16:9) MP4 with English subtitles and an AI end card.

Every model call is logged to `runs.jsonl`, and every output is cached by a hash of its inputs, so changing one line regenerates only what that line affects.

## How it works

```
storyboard.json ──► validate (schema + consent)
      │
      ├─► narration   Gemini TTS, one file per shot
      ├─► reference   FLUX character sheet, you approve one
      ├─► keyframes   FLUX still per shot, same character text + style block
      ├─► shots       Wan 2.2 clips from Kaggle, or a Ken Burns pan if a clip is missing
      ├─► music       ACE-Step candidates from Kaggle, you choose one
      └─► assemble    FFmpeg: duck, subtitles, end card, loudness, 9:16 + 16:9
                            │
                            ▼
              outputs/final/film_9x16.mp4 · film_16x9.mp4
```

| Stage | Model | Runs on | Cost |
|---|---|---|---|
| Storyboard draft | Gemini 3.8 Flash | Gemini API | Free tier |
| Narration | Gemini 3.8 Flash TTS | Gemini API | Free tier |
| Keyframes | FLUX.2 klein 4B | Cloudflare Workers AI | Free daily allowance |
| Moving shots | Wan 2.2 TI2V-5B | Kaggle GPU | Free weekly GPU hours |
| Music | ACE-Step 1.5 | Kaggle GPU | Free weekly GPU hours |
| Assembly | FFmpeg | Your machine | Free |

More detail in [ARCHITECTURE.md](ARCHITECTURE.md).

## Requirements

- Linux or macOS (Windows works through WSL)
- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/) for Python dependencies
- Free accounts: Google AI Studio, Cloudflare, and a phone-verified Kaggle account

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/dagiteferi/AI-Content-Generations.git
cd AI-Content-Generations
```

### 2. Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 3. Install the dependencies

```bash
make install
```

This also installs FFmpeg 9.0.2 through the `imageio-ffmpeg` package, so there is no system FFmpeg to set up. To use your own FFmpeg instead, set `IMAGEIO_FFMPEG_EXE=/path/to/ffmpeg`.

### 4. Get your API keys

```bash
cp .env.example .env
```

Fill in `.env`:

| Variable | Where to get it |
|---|---|
| `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com) → **Get API key** → **Create API key** |
| `CLOUDFLARE_ACCOUNT_ID` | [dash.cloudflare.com](https://dash.cloudflare.com) → account home page, right sidebar |
| `CLOUDFLARE_API_TOKEN` | Profile → **API Tokens** → **Create Token** → **Workers AI** template |
| `KAGGLE_API_TOKEN` | [kaggle.com](https://www.kaggle.com) → **Settings** → verify your phone, then **API** → **Create New Token** (a `KGAT_…` token). Older `kaggle.json` keys go in `KAGGLE_USERNAME` and `KAGGLE_KEY` instead |

`.env` is git-ignored. Never commit it.

### 5. Check that everything works

```bash
make smoke
```

This calls each provider once and logs the latency to `runs.jsonl`. Every row should say `ok`. If one fails, see [Troubleshooting](#troubleshooting).

## Make your film, step by step

### Step 1. Write the story

Fill in `story.md`: whose story it is, the narration language, the audience and the feeling you want at the end. Write the audience and intent in [DESIGN.md](DESIGN.md) **before** generating anything.

If a real person's face or voice appears, record their consent in [ETHICS.md](ETHICS.md) first. The pipeline refuses to run without it.

### Step 2. Draft and check the storyboard

```bash
make draft       # Gemini turns story.md into storyboard.json
make validate    # schema, 8–12 shots, 60–90 s, consent
```

Edit `storyboard.json` by hand as much as you like, then run `make validate` again.

### Step 3. Make the radio cut

```bash
make radio
```

This writes `outputs/radio_cut/radio.mp4`: the narration over placeholder music on a black screen. Play it to at least three people from your audience, and note what they said in `DESIGN.md`.

### Step 4. Make the pictures

```bash
make pictures
```

This makes character reference candidates, then one keyframe per shot. Look at the candidates in `outputs/reference/` and approve the best one:

```bash
uv run heritage approve-reference grandmother 12
```

The approved image is saved in `references/` as the golden reference. Compare every keyframe against it; if a face drifts, change that shot's `keyframe.seed` and run `make pictures` again. Check faces and hands on every keyframe before you spend GPU time on them. Until real clips arrive, each shot gets a Ken Burns pan, so the film is always complete.

### Step 5. Make the moving shots on Kaggle

```bash
uv run heritage gpu export shots          # writes kaggle/bundles/shots.zip
```

Upload the zip to Kaggle, run the notebook as described in [kaggle/README.md](kaggle/README.md), download `out.zip`, then:

```bash
uv run heritage gpu import ~/Downloads/out.zip
```

### Step 6. Make the music on Kaggle

```bash
uv run heritage gpu export music
# run it on Kaggle, then:
uv run heritage gpu import ~/Downloads/out.zip
```

Listen to the candidates in `outputs/music/` under the narration. Set `music.chosen_seed` and `music.choice_reason` in `storyboard.json`.

### Step 7. Assemble the film

```bash
make film
```

This runs every stage. Anything already made is a cache hit, so only the edit is rendered:

- `outputs/final/film_9x16.mp4`, vertical, for phones
- `outputs/final/film_16x9.mp4`, horizontal
- `outputs/final/film.srt`, the subtitles as a separate file

### Step 8. Record the costs

```bash
make costs
```

This writes the calls, latency, GPU minutes and list-price equivalent per stage into [COSTS.md](COSTS.md).

## Change one shot

Edit one keyframe prompt or one narration line in `storyboard.json`, then:

```bash
uv run heritage run --dry-run    # shows what will regenerate
make film
```

Only that shot and the final edit are regenerated. Everything else shows as a cache hit in the output and in `runs.jsonl`.

## Command reference

| Command | What it does |
|---|---|
| `make install` | Install the Python dependencies |
| `make smoke` | Call every provider once |
| `make draft` | Draft `storyboard.json` from `story.md` |
| `make validate` | Check the storyboard and the consent records |
| `make narration` | Narration only |
| `make radio` | Narration and the radio cut |
| `make pictures` | Reference, keyframes and shots |
| `make assemble` | The final edit only |
| `make film` | The whole pipeline |
| `make costs` | Cost table into `COSTS.md` |
| `make test` | Unit tests |

Finer control:

```bash
uv run heritage run --stage narration --shot s03   # one stage, one shot
uv run heritage run --dry-run                      # show what would run, call nothing
uv run heritage run --force                        # ignore the cache
uv run heritage --help                             # every command
```

## Project layout

```
storyboard.json     the film: shots, prompts, seeds, narration, music cues
schema/             JSON Schema generated from the storyboard models
pipeline/           the CLI and one module per stage
kaggle/             GPU scripts for Wan 2.2 and ACE-Step
references/         approved character references
outputs/            everything generated, one folder per stage
runs.jsonl          one line per model call
tests/              unit tests
```

## Troubleshooting

| Problem | Fix |
|---|---|
| `GEMINI_API_KEY is not set` | Fill in `.env` (step 4 of Setup) |
| `FFmpeg not found` | Run `make install` again |
| `consent` error on validate | Add the person's `consent:<id>` row to `ETHICS.md` |
| Cloudflare `429` or quota error | The daily free allowance is used up. Run again tomorrow; finished keyframes are kept |
| Kaggle out of memory | Keep shots at `480p`, or lower `motion.frames` in the storyboard |
| A shot has no Wan clip | It uses the Ken Burns fallback automatically. Export again when you have GPU time |
| No score chosen yet | The film uses placeholder music until `music.chosen_seed` is set |

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md): stages, contracts, caching, failure handling
- [DESIGN.md](DESIGN.md): audience, intent and user tests
- [EXPERIMENTS.md](EXPERIMENTS.md): what was tried and what it showed
- [FAILURES.md](FAILURES.md): what broke and how it was fixed
- [COSTS.md](COSTS.md): measured latency, GPU time and cost
- [ETHICS.md](ETHICS.md): consent, licences and AI labelling
- [REQUIREMENTS.md](REQUIREMENTS.md): requirements mapped to the brief
- [kaggle/README.md](kaggle/README.md): running the GPU stages

## Licences

Wan 2.2 and FLUX.2 klein 4B are Apache 2.0, ACE-Step 1.5 is MIT, and Gemini follows Google's API terms. Every film carries an AI end card and is posted with the platform's AI label switched on. See [ETHICS.md](ETHICS.md).
