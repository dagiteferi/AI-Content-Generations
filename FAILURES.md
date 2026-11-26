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
- **What fixed it / workaround:**
  - A new key in the same project failed the same way: suspension applies to the whole project.
  - Created a new project in AI Studio and a key in it. Text and TTS both answered.
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

### F04: Gemini 3.8 Flash overloaded
- **Date / stage / provider:** 2026-11-25 / smoke / Gemini API
- **What broke:** `gemini-3.8-flash` returned `503: This model is currently experiencing high demand`, or hung past 40 s. `gemini-3.7-flash` and `gemini-flash-latest` also hung. `gemini-3.8-flash-lite` does not exist (404).
- **What I tried:** Listed the models on the key and timed one request to each.
- **What fixed it / workaround:** `gemini-3.5-flash` answered in about 1 s. Text is only used to draft the storyboard, so I set `TEXT_MODEL=gemini-3.5-flash` in `.env`; no code change. TTS (`gemini-3.8-flash-tts`) was not affected.
- **Evidence:** `runs.jsonl`, stage `smoke`, model `gemini-3.8-flash` (503), then `gemini-3.5-flash` (ok)

### F05: Null bytes in runs.jsonl after a restart
- **Date / stage / provider:** 2026-11-25 / logging / local
- **What broke:** `heritage report costs` failed with `JSONDecodeError`. Line 11 of `runs.jsonl` began with 520 null bytes, most likely left by the machine restarting while the file was being written.
- **What fixed it / workaround:** Stripped the null bytes; the record after them was intact, so nothing was lost.
- **Evidence:** `runs.jsonl` line 11 (run `r-20261125-073921`)

### F06: Narration hung on one shot
- **Date / stage / provider:** 2026-11-25 / narration / Gemini TTS (`gemini-3.8-flash-tts`)
- **What broke:** The first full narration run made s01-s08 (most in about 5 s, s07 in 67 s), then waited on s09 for over 10 minutes with no error. The radio cut never started.
- **What I tried:** Found the Gemini client had no time limit, so a stuck request waited forever. Added a 90 s timeout, then found the timeout was not retried: google-genai bundles its own copy of httpx (`httpx2`), so its network errors did not match `httpx.TransportError`.
- **What fixed it / workaround:**
  - 90 s timeout on every Gemini call.
  - The retry check now matches network errors by class name, so a timeout is retried with backoff like a 503.
  - s01-s08 stayed cached, so the re-run only asked for s09.
- **Evidence:** `runs.jsonl`, stage `narration`: s07 `latency_s` 66.9, no line for s09 in that run

### F07: Safety filter flagged a family hug
- **Date / stage / provider:** 2026-11-25 / keyframes / Cloudflare FLUX.2 klein
- **What broke:** For s08 (father embracing his son), seed 1028 returned `400 AiError: Your output has been flagged. Please choose another prompt / input image combination` (code 3030). Seeds 1018 and 1038 of the same prompt passed.
- **What I tried:** Kept the prompt and tried other seeds; those passed, but the son still came out as a child.
- **What fixed it / workaround:** Changed the pose from a close embrace to standing side by side, the father's hand on his shoulder. No further flags, and the pose shows their heights better. Lesson: the filter judges the image, not only the prompt, so an innocent prompt can fail on one seed.
- **Evidence:** test run outside the stage; error id `8e136160-9263-44e7-8949-35f778db95b5`

### F08: TTS hung even with a timeout
- **Date / stage / provider:** 2026-11-25 / narration / Gemini TTS
- **What broke:** After F06's 90 s timeout, s05 still hung for over 6 minutes with nothing logged.
- **What I tried:**
  - A 2 s timeout on a test call did fire (`APITimeoutError`), so the timeout works per read: a reply that trickles in slowly never trips it.
  - `APITimeoutError` comes from the SDK's separate interactions client and was not on the retry list.
  - Rewording s05 did not help, and a line that had worked 10 minutes earlier also hung, so the service itself was overloaded.
  - `gemini-3.1-flash-tts-preview` as a fallback rejects the style instruction (`Speech metadata is not supported for this model`).
- **What fixed it / workaround:**
  - A hard 120 s deadline around each TTS call, plus `TimeoutError` and `APIConnectionError` on the retry list. The run now fails cleanly after 3 logged attempts instead of hanging forever.
  - Waited and re-ran later: spoken lines already made stay cached.
- **Evidence:** `runs.jsonl`, stage `narration`, shot s05: three `TimeoutError` attempts of 120 s each

### F09: Kaggle notebooks had no internet
- **Date / stage / provider:** 2026-11-25 / shots and music / Kaggle
- **What broke:** Both GPU runs failed in their first minutes: `Failed to resolve 'pypi.org'` (pip install diffusers) and `Could not resolve host: github.com` (git clone ACE-Step). Nothing was generated.
- **What I tried:**
  - Confirmed the pushed kernel metadata had `"enable_internet": true`.
  - Verified my phone number on Kaggle and pushed again: same error.
  - A CPU-only probe notebook (no GPU quota used) checked internet every 20 minutes from 16:00 to 23:30. Every check failed.
- **What fixed it / workaround:** The Ken Burns fallback built every shot from its keyframe, so the film was still complete. Next time: test GPU access on day one, and keep Colab ready as a second backend.
- **Evidence:** `kaggle/last-shots-run.log`, `kaggle/last-music-run.log`

### F10: Gemini 3.8 TTS down for hours; switched to 3.1
- **Date / stage / provider:** 2026-11-25 / narration / Gemini TTS
- **What broke:** After F08, `gemini-3.8-flash-tts` timed out on every attempt for over 3 hours, even on a three-word line. Three narration lines (s04, s08, s09) could not be made.
- **What I tried:** Timed one short line on both TTS models: 3.8 timed out at 60 s, while `gemini-3.1-flash-tts-preview` answered in 5 s.
- **What fixed it / workaround:**
  - Re-recorded all six lines with 3.1 so the voice is the same throughout.
  - 3.1 rejects the style instruction, so it is skipped for that model (`NO_STYLE_MODELS`).
  - 3.1 returns bare 16-bit PCM instead of WAV, so FFmpeg could not read its duration. It is now wrapped in a WAV header at the sample rate given in the MIME type.
  - Cost: the voice no longer gets the "calm, warm and serious" instruction, so it may sound flatter.
- **Evidence:** `runs.jsonl`, stage `narration`, model `gemini-3.1-flash-tts-preview`
