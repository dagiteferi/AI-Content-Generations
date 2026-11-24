# Progress

Status as of **2026-11-24 (end of day)**. Phase 1 and 2 code is done; **Phase 3 code** and **all real runs** remain. Deadline: **Thursday 2026-11-26, 23:59 EAT** (both assignments).

## Plan for tomorrow (2026-11-25), in order

| # | Task | Type | Done when |
|---|---|---|---|
| 1 | `sudo apt install ffmpeg`, fill in `.env`, `make smoke` | setup | Every smoke check is ok; record the limits you find in `COSTS.md` |
| 2 | Write the story: `story.md`, `DESIGN.md` §1-2, consent in `ETHICS.md` if needed | you | Audience and feeling written down **before** generating |
| 3 | `make draft` (or edit by hand), then `make validate` | run | Your real storyboard validates |
| 4 | `make radio`, play it to **3+ people**, write user test 1 in `DESIGN.md` | run + you | **Phase 1 checkpoint** |
| 5 | Let Claude read the ACE-Step 1.5 / Wan 2.2 / FLUX.2 docs; wire `acestep_music.py` | code | Music script runs |
| 6 | `make pictures`, then `approve-reference`; check faces and hands | run | A keyframe for every shot |
| 7 | `gpu export shots` → Kaggle → `gpu import`; same for `music`; choose the score | run | **Phase 2 checkpoint** |
| 8 | **Phase 3 code**: assembly stage (both ratios, subtitles, ducking, end card, loudness) | code | `make film` produces two MP4s |
| 9 | User test 2, then the docs, `COSTS.md` and about 10 `EXPERIMENTS.md` entries | run + you | Thursday morning |
| 10 | Post, walkthrough, report, submit both assignments | you | **Thursday 23:59 EAT** |

Steps 1-4 don't depend on any more code, so start there. Step 8 can be coded while Kaggle jobs run in step 7.

## Where things stand

| Item | State |
|---|---|
| Repo | https://github.com/dagiteferi/AI-Content-Generations |
| `main` | Phase 1 + Phase 2 code, all docs (up to date) |
| `phase-1/story-and-radio-cut` | Merged into `main` (PR #2) |
| `phase-2/pictures-and-music` | Merged into `main` (PR #3). Next branch: `phase-3/edit-and-release` from `main` |
| Committer | `dagiteferi <dagiteferi2011@gmail.com>` (repo-local git config) |
| Tests | 31 passing (`make test`) |

## Done

### Setup and docs
- [x] Folder structure from the brief (`pipeline/`, `schema/`, `outputs/`, `kaggle/`, `references/`, `tests/`)
- [x] `REQUIREMENTS.md`: functional and non-functional requirements, mapped to the rubric
- [x] `ARCHITECTURE.md`: stages, contracts, caching, failure handling, `runs.jsonl` format
- [x] `DESIGN.md` template: story, audience, look, two user-test tables, decisions log
- [x] Templates: `EXPERIMENTS.md`, `FAILURES.md`, `COSTS.md`, `ETHICS.md` (with the consent tag rule)
- [x] `.gitignore` (secrets, generated media), `.env.example`

### Phase 1 code
- [x] Storyboard contract (`pipeline/models.py`) and generated JSON Schema (`schema/storyboard.schema.json`)
  - Checks 8-12 shots, a 60-90 s total, unique ids, known characters and unknown fields
- [x] Consent gate: a `real_person` needs `consent:<id>` in `ETHICS.md`, or `validate` and `run` stop
- [x] Core: content-hash cache, atomic writes, a `runs.jsonl` line for every attempt and cache hit, retry with backoff
- [x] Providers: Gemini text, Gemini TTS (`gemini-3.8-flash-tts`), Cloudflare FLUX.1 schnell, Kaggle account check
- [x] `heritage smoke`: one call per provider, with latency logged
- [x] `heritage draft`: Gemini turns `story.md` into `storyboard.json`, feeding validation errors back so it can fix them
- [x] Narration stage: one TTS file per shot, cached by line, voice and style
- [x] Radio cut stage: narration over placeholder music on black 9:16, music ducked under the voice, -14 LUFS, subtitle track, timing table
- [x] CLI flags: `--stage`, `--shot`, `--dry-run`, `--force`; Makefile targets
- [x] Radio cut checked with fake audio and a temporary FFmpeg: 1080x1920, -14.0 LUFS, and the second run is a cache hit

### Not yet tested for real
- [ ] Real API calls: no `.env` keys yet, so Gemini, TTS, FLUX and Kaggle have never run
- [ ] `storyboard.json` is still the **fictional English sample**

## Remaining

### Phase 1: real run still to do (the checkpoint)
1. [ ] Install FFmpeg: `sudo apt install ffmpeg`
2. [ ] `cp .env.example .env` and add the Gemini key, Cloudflare account id and token, and Kaggle username and key
3. [ ] `make smoke`, then record the free-tier limits you find in `COSTS.md`
4. [ ] Decide the story, language, audience and feeling, then fill in `story.md` and `DESIGN.md` sections 1-2
5. [ ] If a real person appears or is voiced: get consent and add a `consent:<id>` row to `ETHICS.md` **first**
6. [ ] `make draft` (or edit `storyboard.json` by hand), then `make validate`
7. [ ] `make radio`, then play `outputs/radio_cut/radio.mp4` to **at least 3 people** from the audience
8. [ ] Write their feedback and the storyboard changes in `DESIGN.md` (user test 1)
9. [x] PR `phase-1/story-and-radio-cut` merged into `main` (PR #2)

### Phase 2: pictures and music (branch `phase-2/pictures-and-music`)

**Done (code, tested with fake media):**
- [x] Contract: `reference_seeds` per character, `motion.frames` (4k+1), `music.seeds`, `chosen_seed` and `choice_reason`
- [x] **Reference stage**: one FLUX candidate per seed; `heritage approve-reference <char> <seed>` copies it to `references/` and updates the storyboard
- [x] **Keyframes stage**: FLUX per shot; the prompt is the shot + character descriptions + "subject centred" + style block
- [x] **Shots stage**: uses the imported Wan clip if there is one, else renders the shot's fallback (Ken Burns following the camera note, or a still)
- [x] **GPU hand-off**:
  - `heritage gpu export shots|music` builds a zip with jobs, images and scripts
  - `kaggle/runner.py` is resumable and writes `results.jsonl`
  - `heritage gpu import out.zip` copies back only expected outputs (stale ones are rejected) and logs GPU seconds
- [x] **Music stage**: lists the candidates per seed and shows the chosen one
- [x] `kaggle/wan_shots.py`: Wan 2.2 TI2V-5B via diffusers (`WanImageToVideoPipeline`)
- [x] `kaggle/README.md`: step-by-step Kaggle guide
- [x] Verified locally: 8 Ken Burns fallbacks render at the right durations; export, then a simulated Kaggle run with an OOM failure, resume and import all work; a real clip takes priority over its fallback

**Remaining:**
- [ ] **Confirm the APIs against the official docs** (reading them was blocked in this session; allow it next time):
  - `kaggle/wan_shots.py`: check the diffusers class names and arguments on the first Kaggle run
  - `kaggle/acestep_music.py`: `generate()` still raises `NotImplementedError`; wire it to the ACE-Step 1.5 API from https://github.com/ACE-Step/ACE-Step-1.5
  - FLUX.2 klein multipart fields, so keyframes can be conditioned on the approved reference image
- [ ] With real keys: `make pictures`, approve a reference, check faces and hands on every keyframe
- [ ] `heritage gpu export shots`, run on Kaggle (480p drafts first), `heritage gpu import`
- [ ] `heritage gpu export music`, run on Kaggle, listen under the narration, set `chosen_seed` and `choice_reason`
- [ ] Write the real experiments in `EXPERIMENTS.md` and blockers in `FAILURES.md` as they happen
- [ ] Checkpoint: a rough cut with a picture for every shot and the chosen score

### Phase 3: edit, release, explain (Thursday)
- [ ] **Assembly stage**:
  - cut the shots to the narration slots and duck the score
  - burn in subtitles, keeping them inside the safe area
  - add a 2-3 s end card and normalise to -14 LUFS / -1 dBTP
  - export **both 9:16 and 16:9**
- [ ] `make film` runs end to end from a clean clone
- [ ] `heritage report costs`: summarise `runs.jsonl` per stage into `COSTS.md`
- [ ] User test 2 with at least 3 people on the near-final cut, recorded in `DESIGN.md`
- [ ] Finalise `README.md`, `ARCHITECTURE.md` and `COSTS.md`; aim for about 10 entries in `EXPERIMENTS.md`
- [ ] Post the film publicly with the platform's **AI label switched on**, writing the post yourself
- [ ] Record the walkthrough (5 min or less): architecture, one hard decision, and a live regeneration of one shot (edit one line, re-run, show that only that shot regenerates in the logs)
- [ ] Write the report (PDF, Word or a link):
  - what you set out to make and for whom, and what the audience told you
  - the hardest problem and how you solved it
  - one practice that helped and one that didn't
  - any ceiling work, and what you'd build next
- [ ] Submit **Assignment 1**: the repo link and the report
- [ ] Submit **Assignment 2**: the 9:16 MP4, plus the 16:9 MP4, the walkthrough and the post as attachments; check every link opens without a login

## Commands

```bash
make install     # uv sync
make smoke       # provider check
make validate    # schema + consent
make draft       # story.md -> storyboard.json
make radio       # narration + radio cut
make pictures    # reference, keyframes, shots (fallbacks until GPU clips arrive)
uv run heritage approve-reference grandmother 12
uv run heritage gpu export shots            # then follow kaggle/README.md
uv run heritage gpu import ~/Downloads/out.zip
make test        # unit tests
uv run heritage run --dry-run              # what would regenerate
uv run heritage run --stage narration --shot s03
```
