# OCR cloud: measured pilot and experimental crop mode

2026-10-16. Images uploaded only after explicit user permission, within the existing
cumulative $0.50 OCR+translation authorization. No private images/crops/patches saved.
Private text, predictions, labels and usage stay in ignored `artifacts/`, not this note.
Primary-source capability/billing/privacy review: [research](cloud-image-ocr-research-20261016.md).

## What is implemented

An **optional experimental crop OCR** adapter for Gemini 3.5 Flash-Lite through
OpenRouter/Vertex. Local detector/grouping and source anchors are unchanged. The
translation model is still independently chosen; DeepSeek remains the existing
translation default. Default OCR is still manga-ocr; this is not a quality promotion.

Settings require BYOK/OpenRouter, text consent **and separate image/fee consent**.
Saving or warming does not call inference or read the API key. Offline resets to
local OCR and clears image consent. The adapter checks consent/mode/engine before
encoding and sending, and after a reply; cancellation rejects late source text.
Settings changes cancel outstanding jobs instead of mixing engine results.

At most four RAM PNG crops/request, <=1,568px edge, <=2.5Mpx and <=2MiB/crop.
No automatic resize, tools, provider fallback, web lookup, crop retry or image generation.
Exact Vertex route, ZDR, denied data collection and prompt/completion price ceilings.
ZDR is the router's endpoint policy, not a claim of no metadata or in-memory caches.

IDs/cardinality/finish/length/schema are checked. Source quotes/expressive spacing
are not stripped. Uncertain OCR preserves the source, disables erasure and automatic
plot memory. A nonblank unreadable crop remains a recoverable deferred source ID.
Cloud OCR boxes are **not** used as glyph masks. Full-page vision localization is
benchmark-only, not a runtime setting.

## Authored controls and actual native pipeline

Haiku: 4/4 authored crop transcriptions exact; two plain blank controls return empty.
Gemini after endpoint fix: 4/4 authored crop transcriptions exact. The first Gemini
attempt was rejected: global catalog advertised temperature, but the chosen Vertex
endpoint did not. Removed that unsupported parameter; privacy was never relaxed.
Gemini blank handling in the runtime is a cheap local blank check, not proof of its
hallucination rate on arbitrary blank/texture images.

Actual development launcher/framing -> PP detector -> Gemini crop OCR -> DeepSeek
translation -> SQLite cache, authored four-bubble image:

| Run | Framed total | Detector | OCR | Translation |
| --- | ---: | ---: | ---: | ---: |
| Cold | 25.545s | 20.349s | 3.553s | 1.571s |
| Warm new page ID | 4.758s | 1.305s | 2.184s | 1.221s |
| Cache revisit | 30.99ms | none | none | none |

Four complete distinct IDs, original source quotes not invented on this run, no API
on the cache revisit. No local OCR weights loaded. This is not personal Edge/MV3
discovery, browser E2E, a controlled A/B speedup, representative manga quality or p95.
The earlier text-only/local-OCR cold run was 39.32s under a different run condition;
do not advertise their difference as a model-only acceleration.

The paid native evidence precedes the final narrow unreadable-source review/opt-out
guards and a 3,000-character response cap; these additions were regression-tested
without another paid call. Evidence retains its actual runtime hash, not relabeled
with the latest source hash. Renderer replay uses the captured actual four-bubble
output, not hand-authored Vietnamese replacements.

## Private benchmark: not perfect, no default change

Fingerprint remains `445d4e457c8ac8c56d8c17e215d683b6abb1a908ba98932729add4f679dbab7f`.
10 supplied pages/81 labels; 8 eligible pages/78 Japanese labels. The size mismatch
and duplicate remain excluded. No usable Vietnamese or clean-background gold, and
Japanese labels are not independently audited. Gold is only used after inference,
never sent in prompts.

| Candidate/run | Coverage completed | Exact against supplied labels | Normalized CER |
| --- | --- | ---: | ---: |
| Earlier manga-ocr GT crops | 78/78 | 48/78 | 9.37% |
| Gemini cloud GT crops | 78/78, 24 requests | 39/78 | 13.31% |
| Haiku cloud GT crops | 36/78 before network stop | 19/36 | 12.86% |

NFKC+whitespace normalization matches the existing crop benchmark. Exact formatting,
expressive spacing and semantic fidelity still require separate review. Gemini median
request latency is 2.583s per batch of up to four crops, **not per crop/page/p95**.
MN109-08 is 5/6 exact, not 6/6. Do not select successful pages to claim full-set quality.

Some supplied labels visibly disagree with the source or omit smaller nearby text
inside their crop (one inspected example: MN109-03/b03). This single-agent visual
inspection is a **review proposal**, not a replacement independent gold set. Some
errors are also real model omissions/substitutions/punctuation changes. Keep both
source and predictions; do not rewrite labels or strip symbols to manufacture a pass.

Full-page Haiku: first normalized-coordinate authored request returned apparent pixel
coordinates and wrong reading order. Switched the experiment to explicit source-pixel
coordinates; private alignment still fails on observed pages. Two private pages
completed (2 supplied labels on MN109-01, 13 on MN109-02); alignment only 2/2 and 8/13,
exact 1/2 and 2/13. A third page and the crop run stopped on network errors. Counts are
diagnostic containment, not detector precision/true recall. No full-page default or
cloud-drawn cleanup was enabled.

## Budget audit

Earlier text/native reservation: $0.0673507. New image pilot reservations:

- Authored initial: $0.0414602 (includes rejected Gemini request with unknown billing).
- Authored corrected endpoint: $0.033726.
- Haiku private crops: $0.0789193 (includes failed network request).
- Haiku private pages: $0.009297 (includes failed network request).
- Gemini all private crops: $0.2125512.
- Native image OCR + translation: $0.0265572.
- Isolated Edge image OCR + translation E2E: $0.0265674, 4 successful responses,
  provider-reported $0.003306106 (not reconciled invoice).

**Cumulative reservation $0.496429 <= $0.50**; provider-reported successful usage
**$0.055663252**, not independently reconciled billing. Remaining reservation
$0.003571 cannot cover a new pipeline at the current conservative ceilings.
Failed/unknown-billed attempts
are not refunded. Earlier aborted-run unused caps are retired; their actual reservations
remain counted. No resetting the budget when moving to another harness/model.

Reservation is not proven spend or an exhausted key/account. It retains the worst-case
token/image/output ceiling even for completed requests, plus unknown-billed attempts.
Successful provider-reported cost is a separate, unreconciled observation. The latest
desktop UI/target-binding work made **no additional paid requests**; totals above are
unchanged. Do not release holds automatically or resume testing from reported usage
alone without reconciling the billing/remaining authorization.

The image benchmark sums prior report reservations before each paid request. Native
image QA includes that session balance and enforces a combined crop+text cap. Old
text-only QA still rejects images before reservation/network; it was not weakened.

## Verification and remaining gates

- Full Python suite: see latest command/result in the demo guide; image consent,
  cancellation, no blank charge, unreadable source retention and no implicit memory
  promotion covered by real seams without live API credentials.
- React options QA desktop/390px: separate consent, disabled save until acknowledged,
  saving causes no paid call, correct saved-engine banner, offline clears crop mode,
  library/context/locked-name controls pass. Console clean. Screenshots RAM-only.
- Full reader UI QA 1280/760/390px: stale results, scroll, resize, source restore,
  late patches, source review and new cloud-uncertain erasure veto pass.
- Actual cloud output lettering replay desktop/mobile: complete text/IDs, no overlap
  or residual Japanese glyphs, original/stop pixel-exact, no external requests.
- Browser plugin absent: isolated Playwright/Edge used. Native/API mocked for frontend
  interactions; the separate paid launcher probe uses real OCR/cloud, not browser discovery.
- A subsequent actual browser/MV3/native/cloud/overlay run passed four authored
  balloons with new-page warm 6.196s, cold 25.624s, cached revisit 0.319s by 250ms
  polling, not first-paint/p95. No personal-profile or real-manga acceptance.
- Previously observed **private mobile 14-pixel/1-channel-level restoration failure**
  is still open; no tolerance change, no claim that it is fixed by this OCR addition.
  Mobile-specific work is now deferred; current MVP acceptance is Windows desktop.
- Real manga grouping, independent Japanese/VI gold, hard semantic-error target,
  fully integrated artwork cleanup and clean-machine packaging are not accepted.

This is a development testing option, not evidence of an instant/perfect release.
