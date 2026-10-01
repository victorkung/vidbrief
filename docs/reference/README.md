# Reference briefs

Production PodBrief (Gemini) briefs for videos we also run through VidBrief. They are a guide for format and voice; VidBrief's local output can be lighter on detail. Compare with `scripts/eval.py` output for the same video.

| File | Video |
|------|-------|
| `podbrief-uZ9Vmp2hZ48.md` | https://www.youtube.com/watch?v=uZ9Vmp2hZ48 (When Shift Happens E182, Jordi Visser, ~65 min) |
| `podbrief-0obQ-vdxPUo.md` | https://www.youtube.com/watch?v=0obQ-vdxPUo (The DeFi Report, Bitcoin vs. Nasdaq, ~37 min) |

## Format VidBrief follows

Only these four parts (no opening or closing lines):

- `## High-Level Overview`: 3 sentences, no bold.
- `## Context`: 2-3 sentence paragraph: who is speaking, their authority, why now.
- `### Chapter N: Title` (no wrapping H2). Each opens with a 2-sentence framing paragraph, then 3-4 bullets: `- [HH:MM:SS] **Label**: one sentence naming who said it.`
- About one chapter per 13 minutes (4 for 37 min, 5 for 65 min).
- `## Key Takeaways`: 4 bullets, `- **Concept**: one sentence.`
