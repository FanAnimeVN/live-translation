# Live translation

Browser extension (Chrome/Edge MV3) that translates raw Japanese manga into Vietnamese in place,
with lettering integrated into the artwork and a per-series story memory. Cloud-first
(account + credits), BYOK and local (Ollama/LM Studio) modes. Product spec: `docs/reference/WISH-FINAL-APP.md`.
Plan and milestones: `docs/DIRECTION.md`. The pre-rewrite prototype lives in `legacy/` (tag `legacy-v0`); do not extend it.

Priority: correct meaning -> lettering integrated into the art -> continuous reading -> extra features.

## Product rules (non-negotiable)

- Privacy: never commit datasets, manga images, API keys or users' story memories. Keys live in
  `.env.local` (dev) or extension storage, never in a bundle or log. At runtime the product keeps manga
  images in memory only; caches store text/geometry, not images. Dev evaluation output goes to `.private/`.
- Offline/local mode never calls a non-localhost host (no cloud API, no metadata lookup).
- No silent charges: saving settings never triggers translation or a request. Extra-cost features
  (premium model, cloud redraw, whole-chapter prefetch) are opt-in with the cost shown first.
- Story memory: every remembered name/term/address rule/event has evidence (page + region) and a
  chapter/page cutoff. Only use memory known before the current reading position; prefetching is not reading.
  Unknown speakers/genders/relationships stay unknown. Reader locks always beat model proposals and keep history.
- Address terms are directed (A->B); never derive B->A automatically.
- Keep meaningful Japanese honorifics/vocatives (-san, -kun, -chan, -sama, senpai, sensei, onii-chan, nee-chan).
  A retained sibling vocative already carries its title: "nee-chan", never "chị nee-chan"/"chị gái nee-chan";
  "onii-chan", never "anh onii-chan"/"anh trai onii-chan". Do not strip legitimate Vietnamese pronouns elsewhere.
- Preserve delivery: stutters, elongation, ellipses, !?, spaced/spelled words, CAPS. Do not delete source
  punctuation or quotes to hide OCR errors.
- Never silently drop text (small text, signs, narration may matter). Erase art only where text separation is
  safe; otherwise keep the original art and offer a reversible annotation. "View original" restores the exact source.
- Model files are pinned (revision + SHA-256); inference never downloads executable code.

## Engineering

- One TypeScript stack: `packages/core` (pure, runs in browser and Node), `packages/render`, `apps/*`, `tools/eval`.
- Evaluate on real pages (private GT set, Manga109) and report measured numbers with their conditions
  (model, run count, cold/warm/cache). Targets are targets, not results. Report hard cases separately.
- OCR labels may be wrong: record adjudications separately, never edit the source dataset.
- Prefer small, real end-to-end slices over probes. Test in a real browser at every milestone.
- Paid API usage is logged in `.private/ledger.jsonl`; stop at the budget in `.env.local` unless the user raises it.
- Build and test (`npm run check`) before saying something works.
