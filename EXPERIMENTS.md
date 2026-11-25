# Experiments

Target: about 10 entries. Change one thing at a time and keep the seed fixed. Evidence = `runs.jsonl` lines or output paths.

## Template
### E01: <title>
- **Date:**
- **Hypothesis:**
- **Change:** (one variable)
- **Fixed:** (seed, model, other params)
- **Result:** (evidence: run_id / output paths)
- **Decision:**

### E01: Male narrator voice
- **Date:** 2026-11-25
- **Hypothesis:** The narrator is the son ("my father said to me"), so a male voice will sound more natural than the default female one.
- **Change:** `voice.voice_name` from `Sulafat` to `Charon`.
- **Fixed:** model `gemini-3.8-flash-tts`, same style instruction, same s02 line.
- **Result:** s02 came out at 8.8 s in the male voice and fits its 9 s shot. Listening: _add your verdict_.
- **Decision:** Keep `Charon`.

### E02: Let the narration set the shot lengths
- **Date:** 2026-11-25
- **Hypothesis:** The planned durations from the draft are guesses; the measured narration should decide them.
- **Change:** Built the radio cut, read its timing table, then set s01 to 8.0 s, s02 to 9.5 s and s09 to 9.0 s.
- **Fixed:** All narration audio (every line a cache hit, no new TTS call).
- **Result:** Before: 75.9 s with 3 shots over plan (+0.9, +0.2, +0.9 s). After: 76.5 s with no overruns.
- **Decision:** Keep the new lengths, so keyframes and clips are made at the right length.

### E03: Making the characters look Ethiopian
- **Date:** 2026-11-25
- **Hypothesis:** "Ethiopian" alone is too weak for FLUX.2 klein; naming Habesha / East African features, skin tone and hair texture will fix the faces.
- **Change:** Only the character description, three versions:
  - A: "Ethiopian young man with short black hair…" (the draft)
  - B: "Habesha young man from Ethiopia, East African features, deep brown skin, short tightly coiled black hair…"
  - C: B plus "Addis Ababa, Horn of Africa, high cheekbones, slender build"
- **Fixed:** seed 12, `@cf/black-forest-labs/flux-2-klein-4b`, same framing and style block.
- **Result:**
  - A: all 4 student and 4 father portraits looked South Asian, not Ethiopian.
  - B: clearly Habesha.
  - C: also Habesha, but a deformed hand appeared in front of the chest; more words gave the model more to get wrong.
  - Father with the B-style description (seeds 21, 22): Habesha features and a white gabi with a woven border.
- **Decision:** Use B for both characters. A one-word nationality is not enough; describe the features.

### E04: Making the places look Ethiopian
- **Date:** 2026-11-25
- **Hypothesis:** Like the faces (E03), "Ethiopian home" and "brick school hall" will come out generic. Naming concrete local details will place the film in Ethiopia.
- **Change:** Rewrote every keyframe prompt with a few specific details: plastered blue walls, corrugated iron roofs, blue metal gates, eucalyptus trees, a jebena coffee pot and mesob basket, a kerosene lamp, single-storey school blocks with blue doors. The style block now says "set in Addis Ababa, Ethiopia".
- **Fixed:** seeds, model `@cf/black-forest-labs/flux-2-klein-4b`, character descriptions.
- **Result:** s01, s03 and s07 now show recognisably Ethiopian streets and schools. Two new problems: s07 showed a paper with tiny unreadable text, and s01 had people at the gate on a "quiet" night.
- **Decision:** Keep the detailed prompts. s07 now holds a pencil case instead of paper (no text in images), and s01 says "empty street, nobody outside".

### E05: Why the son kept looking like a child
- **Date:** 2026-11-25
- **Hypothesis:** Writing "his 18-year-old son, a young adult as tall as his father" will make s08 show a young man.
- **Change:** Three prompt versions for s08, each tried on seeds 1008, 1018 and 1038:
  - A: "embracing his son" (the draft)
  - B: "his 18-year-old son, a young adult as tall as his father, standing side by side"
  - C: no word "son": "an older man… and a tall young man of about 20 with a light moustache, slightly taller than the older man"
- **Fixed:** model, style block, character descriptions.
- **Result:**
  - A: a boy of about 12.
  - B: still a boy of 12-15 on all three seeds; the age in the prompt did not override the word "son".
  - C: young adults on 2 of 3 seeds; seed 1038 had both characters right.
- **Decision:** Use C with seed 1038. The relationship word ("son") pulled the model toward a child harder than the stated age did; describe what the viewer sees, not who the person is. The same fix worked for s02, and "still life, no people" fixed s04 and s09, where strangers had appeared at the table.

### E06: Show, don't tell
- **Date:** 2026-11-25
- **Hypothesis:** The first cut narrated what the picture already showed ("the pencil grew shorter"). Fewer, quieter lines and silent shots will feel more artistic and let the images carry the story.
- **Change:**
  - Narration made optional per shot in the contract (`narration: null` gives a silent shot with no subtitle).
  - Narration cut from 9 lines (82 words) to 5 short lines (about 30 words). s01, s04, s06 and s07 are silent; the pencil, the lamp and the walk to the exam tell their part alone.
  - Silent shots shortened (s01 6 s, s04 5 s, s06 6 s, s07 7 s): 76.5 s → 71.5 s.
- **Fixed:** keyframes, voice, music cue.
- **Result:** _fill in after the radio cut and user test 1_
- **Decision:** _pending_

