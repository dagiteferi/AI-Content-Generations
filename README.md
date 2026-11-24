# Heritage Short

A CLI pipeline that turns `storyboard.json` into a 60–90 s narrated, scored and subtitled short film, exported in 9:16 and 16:9. Every stage reads the storyboard, writes to `outputs/`, caches by content hash and logs each model call to `runs.jsonl`.

## Requirements
- Python 3.12+ and [uv](https://docs.astral.sh/uv/)
- FFmpeg (`sudo apt install ffmpeg`)
- Free accounts: Gemini API key (Google AI Studio), Cloudflare (account id + Workers AI token), phone-verified Kaggle

## Setup
```bash
git clone https://github.com/dagiteferi/AI-Content-Generations.git
cd AI-Content-Generations
cp .env.example .env      # fill in your keys
make install
make smoke                # one call per provider, latency logged to runs.jsonl
```

## Usage
| Command | What it does |
|---|---|
| `make validate` | Validate `storyboard.json` against the schema and consent records |
| `make draft` | Draft `storyboard.json` from `story.md` with Gemini |
| `make narration` | Generate narration per shot (Gemini TTS) |
| `make radio` | Narration + placeholder music on black → `outputs/radio_cut/radio.mp4` |
| `make pictures` | Reference candidates, keyframes, and shots (Ken Burns until GPU clips arrive) |
| `make film` | Run every implemented stage end to end |
| `make test` | Unit tests |

Finer control:
```bash
uv run heritage run --stage narration --shot s03   # one stage, one shot
uv run heritage run --dry-run                      # what would regenerate, no calls
uv run heritage run --force                        # ignore the cache
```

Edit one narration line in `storyboard.json` and re-run: only that shot's narration and the radio cut regenerate.

GPU stages (video, music) run on Kaggle through a zip hand-off. See [kaggle/README.md](kaggle/README.md):
```bash
uv run heritage approve-reference grandmother 12   # pick the golden reference
uv run heritage gpu export shots                   # -> kaggle/bundles/shots.zip
uv run heritage gpu import ~/Downloads/out.zip     # clips become cache hits
```

## Status
- [x] Phase 1: contract, schema, smoke test, storyboard drafting, narration, radio cut
- [x] Phase 2 (code): reference sheet, keyframes, Kaggle hand-off, Ken Burns fallback, music candidates
- [ ] Phase 2 (run): real keyframes, Wan clips on Kaggle, ACE-Step wiring
- [ ] Phase 3: assembly, both aspect ratios, end card

## Docs
- [REQUIREMENTS.md](REQUIREMENTS.md): functional and non-functional requirements
- [ARCHITECTURE.md](ARCHITECTURE.md): stages, contracts, caching, failure handling
- [DESIGN.md](DESIGN.md): audience, intent, user tests
- [EXPERIMENTS.md](EXPERIMENTS.md) · [FAILURES.md](FAILURES.md) · [COSTS.md](COSTS.md) · [ETHICS.md](ETHICS.md)
