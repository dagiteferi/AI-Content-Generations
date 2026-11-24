# Design

> **Rule:** the audience and intent are written **before** anything is generated. The user tests below are dated, and each one ends with what changed in `storyboard.json`.

## 1. The story

| | |
|---|---|
| **Working title** | _TODO_ |
| **Whose story** | _TODO: person, place or family story_ |
| **Logline** (one sentence) | _TODO_ |
| **Narration language** | _TODO (e.g. Amharic)_, with English subtitles |
| **Source** | _TODO: who told the story, when, and how (interview, voice note…)_ |

### Treatment (3–5 sentences, one beat each)
1. _TODO_
2. _TODO_
3. _TODO_
4. _TODO_
5. _TODO_

## 2. Audience and intent (the brief)

| | |
|---|---|
| **Who watches** | _TODO (e.g. cousins in the diaspora, aged 18–35)_ |
| **Where they watch** | _TODO (e.g. a phone, Telegram/TikTok, vertical, often muted at first)_ |
| **What they should feel or understand at the end** | _TODO: one feeling_ |
| **Problem statement** | How might we help _[audience]_ feel _[feeling]_ about _[story]_? |
| **Constraints** | 60–90 s · free models only · 3 days · consent required for real people |

### Design consequences of the brief
- Vertical (9:16) is the primary format, with subjects kept centred so a 16:9 export works from the same material.
- Subtitles are always on, at most 2 lines of 40 characters, inside the safe area (many viewers start muted).
- _TODO: add consequences once the audience is fixed_

## 3. Look and sound

| | |
|---|---|
| **Style block** (added to every image prompt) | _TODO (e.g. "warm hand-painted illustration, soft golden-hour light, muted earth palette, gentle film grain")_ |
| **Main character description** | _TODO_ |
| **Golden reference** | `references/_TODO_.png` (approved on _date_) |
| **Voice** | _TODO: voice name, plus a style instruction such as "calm, warm, unhurried"_ |
| **Score** | _TODO: e.g. "sparse krar and soft strings, 70 bpm, no lead melody under the voice, theme returns at the end"_ |

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
| | | | |
