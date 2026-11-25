# Failures

Real blockers (quota, memory, consistency, language…), what was tried, and what fixed it or worked around it.

## Template
### F01: <title>
- **Date / stage / provider:**
- **What broke:** (exact error)
- **What I tried:**
- **What fixed it / workaround:**
- **Evidence:** (runs.jsonl run_id)

### F01: Gemini key rejected, project suspended
- **Date / stage / provider:** 2026-11-25 / smoke / Gemini API
- **What broke:** `403 PERMISSION_DENIED: Consumer 'projects/…' has been suspended` (`CONSUMER_SUSPENDED`) for both text and TTS.
- **What I tried:** The key itself is valid; the Google Cloud project behind it is suspended.
- **What fixed it / workaround:** _Pending:_ a new key from a fresh project in AI Studio.
- **Evidence:** `runs.jsonl`, stage `smoke`, models `gemini-3.8-flash` and `gemini-3.8-flash-tts`

### F02: FLUX.1 schnell no longer accepts a seed
- **Date / stage / provider:** 2026-11-25 / smoke / Cloudflare Workers AI
- **What broke:** `400 Bad Request`, `AiError: Additional or unevaluated properties '/seed' at '/' not allowed`. The model's input schema now allows only `prompt` and `steps`.
- **What I tried:**
  - Without `seed` it works, but then no keyframe can be pinned to a seed.
  - Listed the Workers AI FLUX models and found FLUX.2 klein 4B (Apache 2.0). It takes multipart form fields instead of JSON.
  - Sent the same prompt and seed to klein twice: the two images differed, and an unknown field was silently accepted. So the seed is not a reproducibility guarantee on this endpoint either.
- **What fixed it / workaround:**
  - Switched the default image model to `@cf/black-forest-labs/flux-2-klein-4b`, with a multipart request; schnell is still supported, without a seed.
  - Reproducibility now rests on the cache: each keyframe file is kept and keyed by prompt + seed, so a re-run reuses it instead of calling the model.
  - Klein also accepts reference images, which opens the way to conditioning keyframes on the approved character reference.
- **Evidence:** `runs.jsonl`, stage `smoke`, model `@cf/black-forest-labs/flux-1-schnell` (error), then `flux-2-klein-4b` (ok)

### F03: Kaggle's new API token format
- **Date / stage / provider:** 2026-11-25 / smoke / Kaggle
- **What broke:** Kaggle now issues a single `KGAT_…` API token instead of a `kaggle.json` username + key pair, so the account check had nothing to authenticate with.
- **What fixed it / workaround:** Added `KAGGLE_API_TOKEN`, sent as a bearer header; the old username + key still works.
- **Evidence:** `runs.jsonl`, stage `smoke`, provider `kaggle`, status ok
