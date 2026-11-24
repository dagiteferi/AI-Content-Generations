# Progress

Status as of **2026-11-24**. Deadline: **Thursday 2026-11-26, 23:59 EAT** (both assignments).

## Where things stand

| Item | State |
|---|---|
| Repo | https://github.com/dagiteferi/AI-Content-Generations |
| `main` | Docs and folder structure |
| `phase-1/story-and-radio-cut` | Phase 1 code, pushed. **Pull request not opened yet** |
| Committer | `dagiteferi <dagiteferi2011@gmail.com>` (repo-local git config) |
| Tests | 17 passing (`make test`) |

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

### Tomorrow morning: finish Phase 1 (the checkpoint)
1. [ ] Install FFmpeg: `sudo apt install ffmpeg`
2. [ ] `cp .env.example .env` and add the Gemini key, Cloudflare account id and token, and Kaggle username and key
3. [ ] `make smoke`, then record the free-tier limits you find in `COSTS.md`
4. [ ] Decide the story, language, audience and feeling, then fill in `story.md` and `DESIGN.md` sections 1-2
5. [ ] If a real person appears or is voiced: get consent and add a `consent:<id>` row to `ETHICS.md` **first**
6. [ ] `make draft` (or edit `storyboard.json` by hand), then `make validate`
7. [ ] `make radio`, then play `outputs/radio_cut/radio.mp4` to **at least 3 people** from the audience
8. [ ] Write their feedback and the storyboard changes in `DESIGN.md` (user test 1)
9. [ ] Open the PR `phase-1/story-and-radio-cut` → `main` and merge it

### Phase 2: pictures and music (branch `phase-2/pictures-and-music`)
- [ ] Research the current APIs first: Wan 2.2 TI2V-5B (diffusers or the CLI on a T4), ACE-Step 1.5 (install and parameters), and the FLUX.2 klein multipart fields for reference images
- [ ] **Reference stage**: character and style candidates with FLUX; approve one and save it as `references/<character>.jpg`
- [ ] **Keyframes stage**: one still per shot, with the style block and character text added to every prompt (and the reference image, if FLUX.2 klein allows it); keep subjects centred for 9:16 and 16:9
- [ ] **Shots stage**:
  - `heritage gpu export` writes the jobs and keyframes as a bundle for Kaggle
  - `kaggle/wan_shots.py` runs Wan 2.2 at 480p and saves each clip as soon as it's done
  - `heritage gpu import` brings the clips back as cache hits and logs GPU seconds
- [ ] **Ken Burns fallback**: rendered locally with FFmpeg `zoompan` for any shot that has no clip
- [ ] **Music stage**: `kaggle/acestep_music.py` makes 3 candidates; choose one in `storyboard.json` (`music.chosen` and `choice_reason`)
- [ ] Log every experiment in `EXPERIMENTS.md` and every blocker in `FAILURES.md`, as they happen
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
make test        # unit tests
uv run heritage run --dry-run              # what would regenerate
uv run heritage run --stage narration --shot s03
```
