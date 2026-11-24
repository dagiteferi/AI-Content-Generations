# Requirements

System requirements for **Heritage Short**: a CLI pipeline that turns `storyboard.json` into a 60–90 second narrated, scored and subtitled short film.

Each requirement has an ID so code, tests and docs can refer to it. The **Source** column points to the part of the challenge brief or grading rubric it comes from.

---

## 1. Functional requirements

### 1.1 Storyboard (the contract)

| ID | Requirement | Source |
|---|---|---|
| FR-01 | The system reads a single `storyboard.json` as the only input that describes the film. | "one file is the contract between every stage" |
| FR-02 | The storyboard is validated against `schema/storyboard.schema.json` before any stage runs. An invalid storyboard stops the run with a clear error that names the field. | "validated before every run" |
| FR-03 | The storyboard holds 8–12 shots. Each shot has: id, duration, purpose (why it exists), shot size and camera, keyframe prompt, motion prompt, seed, narration line (source language + English subtitle) and fallback policy. | Phase 1 step 4; "every shot has a stated reason" |
| FR-04 | The storyboard holds global settings: title, language, TTS voice and style instruction, style block, character descriptions, reference images, music cues, and the target total duration (60–90 s). | Appendix B: style block, character sheet |
| FR-05 | The JSON Schema is generated from the code's data models, so the schema and the code cannot drift apart. | SE quality |

### 1.2 Stages

| ID | Requirement | Source |
|---|---|---|
| FR-10 | **Narration stage:** generate one audio file per shot from the narration line with Gemini TTS, using the voice and style instruction from the storyboard. | Phase 1 step 5 |
| FR-11 | Measure each narration clip's real duration and report shots whose narration is longer than the shot duration. | Appendix B: "time the narration first" |
| FR-12 | **Radio cut:** assemble the narration over placeholder music on a black screen into a playable file. | Phase 1 step 5 |
| FR-13 | **Reference stage:** generate the character and style reference sheet from the storyboard before any keyframe. | Phase 2 step 1 |
| FR-14 | **Keyframes stage:** generate one still per shot with FLUX on Cloudflare Workers AI. Every prompt gets the style block and the character description added. | Phase 2 step 1 |
| FR-15 | **Shots stage:** turn each keyframe plus its motion prompt into a short clip with Wan 2.2 TI2V-5B on Kaggle or Colab. | Phase 2 step 2 |
| FR-16 | When a clip fails or the GPU quota is exhausted, the shot falls back to a Ken Burns pan/zoom over its keyframe, made with FFmpeg. | "The path" fallback |
| FR-17 | **Music stage:** generate N (default 3) ACE-Step score candidates from the music cues. The chosen one is selected in the storyboard and the reason is recorded. | Phase 2 step 3 |
| FR-18 | **Assembly stage:** cut the shots to narration timing, mix the narration and the music with the music ducked under the voice (sidechain compression), burn in English subtitles, normalise loudness to −14 LUFS with true peak ≤ −1 dBTP, and append an AI end card of 2–3 s. | Phase 3 step 1 |
| FR-19 | Export both **9:16 (vertical)** and **16:9 (horizontal)** H.264/AAC MP4s from the same material. | "What you will build" |
| FR-20 | Keep subtitles to at most 2 lines of about 40 characters each, inside the vertical safe area. | Appendix B |

### 1.3 CLI

| ID | Requirement | Source |
|---|---|---|
| FR-30 | A single command (`make film`) runs the whole pipeline end to end from a clean clone. | "run one command" |
| FR-31 | `heritage validate` validates the storyboard only. | — |
| FR-32 | `heritage run --stage <name>` runs a single stage. | Re-run one stage |
| FR-33 | `heritage run --shot <id>` regenerates only one shot across all stages. | Walkthrough live regeneration |
| FR-34 | `heritage smoke` calls each provider once and logs its latency. | Phase 1 step 1 |
| FR-35 | `--dry-run` shows which outputs would be regenerated and which are cached, without calling any model. | Explains caching on camera |
| FR-36 | `--force` ignores the cache for the selected stage or shot. | — |

### 1.4 Caching, logging, measurement

| ID | Requirement | Source |
|---|---|---|
| FR-40 | Every generated artefact is cached under a key that is a hash of everything that affects it (prompt, seed, model, parameters, upstream input files). A re-run regenerates only artefacts whose key changed. | "caching so a re-run only regenerates what changed" |
| FR-41 | Every model call appends one line to `runs.jsonl` with: timestamp, run id, stage, shot, provider, model, parameters, seed, cache hit/miss, latency, GPU seconds (where known), list-price cost equivalent, status, error and output path. | "a log line for every model call" |
| FR-42 | `heritage report costs` summarises `runs.jsonl` per stage (calls, latency, GPU minutes, cost) to feed `COSTS.md`. | Measurement criterion |

---

## 2. Non-functional requirements

### 2.1 Reproducibility

| ID | Requirement |
|---|---|
| NFR-01 | Prompts, seeds and parameters live in `storyboard.json`, not in code. The same storyboard with the same seeds gives the same keyframes and music within model determinism. |
| NFR-02 | Dependencies are pinned (`uv.lock`), and the README states the Python and FFmpeg versions. |
| NFR-03 | Assembly is deterministic: the same inputs give the same output file. |

### 2.2 Reliability and failure handling

| ID | Requirement |
|---|---|
| NFR-10 | Every network call is retried with exponential backoff on transient errors (timeouts, 429, 5xx). Each shot gets at most 3 attempts. |
| NFR-11 | When retries run out, the stage applies the shot's fallback (for example Ken Burns), logs it, and continues. One failed shot never stops the film from rendering. |
| NFR-12 | Outputs are written atomically (temp file, then rename), so an interrupted run never leaves a corrupt file in the cache. |
| NFR-13 | GPU notebooks save each clip as soon as it is done, so a session timeout loses at most one clip. |
| NFR-14 | Errors name the stage, the shot and the provider, and suggest a next step. |

### 2.3 Security and privacy

| ID | Requirement |
|---|---|
| NFR-20 | API keys come only from environment variables or `.env`. `.env` is in `.gitignore`, and `.env.example` documents the required keys without values. |
| NFR-21 | No secrets appear in `runs.jsonl` or in logs. |
| NFR-22 | Private family details are kept out of prompts sent to free endpoints that may train on inputs. |

### 2.4 Cost and performance

| ID | Requirement |
|---|---|
| NFR-30 | Total running cost is zero, using free tiers only. |
| NFR-31 | Video is drafted at 480p and only the chosen shots are rendered at 720p, to stay within the Kaggle quota of about 30 GPU hours a week. |
| NFR-32 | A fully cached re-run of the whole pipeline (assembly only) finishes in under 2 minutes on a laptop. |
| NFR-33 | Calls respect each provider's rate limits and stop cleanly when a daily allowance (for example Cloudflare's) runs out. |

### 2.5 Maintainability

| ID | Requirement |
|---|---|
| NFR-40 | Every model sits behind a provider interface, so swapping a model (for example Wan → HunyuanVideo) changes one adapter and the storyboard, not the stages. |
| NFR-41 | Stages communicate only through `storyboard.json` and files in `outputs/`. No stage imports another stage. |
| NFR-42 | Code is typed, and unit tests cover schema validation, cache keys and assembly timing. |

### 2.6 Usability and documentation

| ID | Requirement |
|---|---|
| NFR-50 | A stranger can follow the README from clone to film without help. |
| NFR-51 | The CLI prints progress per stage and shot, and marks each one as cached, generated or fallback. |

### 2.7 Ethics and compliance

| ID | Requirement |
|---|---|
| NFR-60 | Consent from every real person shown or voiced is recorded in `ETHICS.md` **before** anything of them is generated. The pipeline refuses to run if the storyboard lists a real person without a consent record. |
| NFR-61 | The licence of every model and output is recorded in `ETHICS.md`. |
| NFR-62 | The final film carries an AI end card, and SynthID/C2PA metadata is preserved where present. |

---

## 3. Out of scope

- A web API or UI (optional ceiling work, only if time allows).
- Databases or queues: files and `runs.jsonl` are the state.
- Training models (a LoRA is optional ceiling work).

## 4. Traceability to the grading rubric

| Rubric criterion | Requirements |
|---|---|
| Software engineering & reproducibility (20) | FR-01–05, FR-30–36, FR-40–41, NFR-01–03, NFR-10–13, NFR-20 |
| Documentation (10) | NFR-50, ARCHITECTURE.md |
| Design thinking & audience (10) | FR-03 (purpose per shot), FR-12, DESIGN.md |
| Experimentation (10) | FR-41, EXPERIMENTS.md |
| Troubleshooting (10) | NFR-11, NFR-14, FAILURES.md |
| Measurement (5) | FR-41, FR-42, COSTS.md |
| Consent, labelling, licences (5) | NFR-60–62 |
