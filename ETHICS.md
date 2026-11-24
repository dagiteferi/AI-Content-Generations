# Ethics: consent, licences, labelling

## Consent (recorded BEFORE generating anything of a real person)
| Tag | Person (role) | Appears as | Consent for | How recorded | Date | Words in their mouth approved? |
|---|---|---|---|---|---|---|
| | | face / likeness / voice / story | | | | |

> **Gate:** for every character with `"real_person": true`, the pipeline looks for the tag
> `consent:<consent_ref>` in this file (e.g. `consent:grandmother` in the Tag column).
> `heritage validate` and `heritage run` stop if the tag is missing.

## Licences
| Model / tool | Licence | Output usage |
|---|---|---|
| Gemini 3.8 Flash / TTS | Google API terms | |
| FLUX.1 schnell / FLUX.2 klein 4B | Apache 2.0 | |
| Wan 2.2 TI2V-5B | Apache 2.0 | |
| ACE-Step 1.5 | MIT | Outputs usable commercially |
| FFmpeg | LGPL/GPL | |

## Labelling plan
- AI end card in the film itself.
- Platform AI-content disclosure switched on when posting.
- Watermarks / SynthID / C2PA metadata kept intact.

## Private data
- Private family details kept out of prompts sent to free endpoints that may train on inputs.
