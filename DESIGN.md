# Design

> **Rule:** the audience and intent are written **before** anything is generated. The user tests below are dated, and each one ends with what changed in `storyboard.json`.

## 1. The story

| | |
|---|---|
| **Working title** | የመጨረሻው ምዕራፍ (The Final Chapter) |
| **Whose story** | Two sayings my father told me the night before my Grade 12 national exam |
| **Logline** (one sentence) | A student who laughed the year away hears a father's warning, opens the book, and learns that the final chapter does not forgive jokes |
| **Narration language** | Amharic, with English subtitles |
| **Source** | My own memory of my father's words before my Grade 12 national exam. The characters are fictional and inspired by my family |

### Treatment (one beat each)
1. **The warning.** Late at night a father tells his child: "ፈተና ቀልድ አያውቅም፤ ውጤትም ይቅርታ የለውም."
2. **The mistake.** Months earlier the student laughed with friends and left the books closed.
3. **The turn.** As the exam comes close the words come back; the student studies every night and the pencil grows short.
4. **The exam.** On exam morning the student walks in calm and ready.
5. **The meaning.** On results day the father smiles: "የመጨረሻው ምዕራፍ ቀልድ አይወድም." The narrator turns to the viewer: your final chapter has already started.

## 2. Audience and intent (the brief)

| | |
|---|---|
| **Who watches** | Ethiopian Grade 12 students and final-year university students facing the exit exam (about 17–24), and their parents. They follow my channel |
| **Where they watch** | On a phone: TikTok, YouTube Shorts and Telegram. Vertical, often muted for the first seconds, scrolling fast |
| **What they should feel or understand at the end** | A quiet seriousness, then hope: "my final chapter has started; tonight I open the book" |
| **Problem statement** | How might we help Ethiopian exam students feel that the time to prepare is now, without scaring them, through the words their own parents say? |
| **Constraints** | 60–90 s · free models only · 3 days · no real faces or voices · Amharic TTS quality unknown |

### Design consequences of the brief
- Vertical (9:16) is the primary format, with subjects kept centred so a 16:9 export works from the same material.
- Subtitles are always on, at most 2 lines of 40 characters, inside the safe area (many viewers start muted, and parents abroad may not read Amharic).
- The first shot must hook in under 3 seconds: the first saying is heard early, in shot 2, not at the end.
- Both sayings are spoken in Amharic, because the audience already knows them from home; the English subtitles make the film shareable beyond them.
- A hopeful ending and no failure scene: the audience is anxious already, and the film should push them to start, not frighten them.
- The last line speaks to the viewer directly and names both exams, so Grade 12 and exit-exam students both feel it is for them.
- Time passing is shown with a pencil that grows shorter, not a calendar, because the image model garbles text.

## 3. Look and sound

| | |
|---|---|
| **Style block** (added to every image prompt) | "cinematic realistic digital painting, warm amber lamp light at night, soft golden morning light, muted earth tones, gentle film grain". Painted realism rather than photographs, because photoreal faces drift more between shots and it avoids looking like a real person |
| **Main character description** | An Ethiopian student about 18 in a plain shirt, and the father in his fifties in a simple gabi or jacket. Both are described the same way in every prompt |
| **Golden reference** | `references/<student>.jpg`, to be approved after `make pictures` |
| **Voice** | Gemini TTS, one calm narrator, "calm, warm and serious, like a father speaking at night". To be checked by native Amharic listeners at the radio cut |
| **Score** | Quiet and serious: soft piano and strings with a slow masinko or krar texture, about 70 bpm, no lead melody under the voice, rising gently on exam day and resolving at the end |

## 4. Shot list (reasons)

Every shot needs a reason. The full prompts live in `storyboard.json`.

| Shot | Size / camera | Purpose (why it exists) |
|---|---|---|
| s01 | _TODO_ | _TODO_ |
| … | | |

## 5. User test 1: radio cut

- **Date:**
- **Version tested:** `outputs/radio_cut/radio.mp4` (storyboard commit `_hash_`)
- **Testers (≥3, from the audience):**

| # | Who (role, not name) | How (in person / Slack) | What they said | Where they reacted |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |

**Insights:**
- _TODO_

**What changed in the storyboard because of it:**
| Change | Because | Commit |
|---|---|---|
| | | |

## 6. User test 2: near-final cut

- **Date:**
- **Version tested:** `outputs/final/film_9x16.mp4` (commit `_hash_`)

| # | Who | How | What they said | Where they reacted |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |

**Insights:**
- _TODO_

**What changed:**
| Change | Because | Commit |
|---|---|---|
| | | |

## 7. Decisions log

| Date | Decision | Alternatives considered | Why |
|---|---|---|---|
| 2026-11-24 | CLI pipeline (Python + typer), no web framework | FastAPI service | The brief requires one command from a clean clone. A server adds setup without adding value to the film |
| 2026-11-24 | Square keyframes and clips, subject centred | Separate 9:16 and 16:9 generations | One generation serves both exports and halves the GPU time; the cost is resolution in the crops |
| 2026-11-24 | File-based GPU hand-off (export zip → Kaggle → import) | Driving Kaggle through its API | Works with the free tier and a phone-verified account, and every GPU job still lands in runs.jsonl |
| 2026-11-24 | Ken Burns fallback per shot until a clip arrives | Block the edit until all clips exist | There is always a complete rough cut, whatever the GPU quota |
| 2026-11-25 | FFmpeg from the `imageio-ffmpeg` Python package | System FFmpeg (`apt`/`brew`); a Docker image | `make install` alone sets up everything, the FFmpeg version is pinned in `uv.lock`, and it has every filter the edit needs (subtitles, sidechaincompress, loudnorm, zoompan). It has no `ffprobe`, so durations are read from FFmpeg's own header line |
