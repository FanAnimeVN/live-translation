# Cloud page-proposal detector — 2026-10-17

This is an opt-in recall experiment for the cloud-first MVP. It is not the
default detector and it has not yet been run against the private pages.

## Contract

- The user must separately enable cloud mode, BYOK OpenRouter, general cloud
  consent and **full-page image consent**. Saving settings never sends a
  request.
- Warmup only checks consent. The first request occurs during page processing.
- The image is resized only in a temporary RAM copy to the reviewed vision
  limits; returned boxes are mapped to the original source dimensions.
- The model receives one page and returns bounded text boxes. Each result is a
  `cloud_page_proposal` review region with unknown speaker/listener, no balloon
  mask, no erasure permission and no story-memory authority.
- Local OCR still runs on the proposed source crop. A cloud proposal cannot
  overwrite an existing reader source key or silently hide artwork.
- Provider fallbacks are disabled, the endpoint is OpenRouter with the selected
  vision model, and the request has an explicit price ceiling. Cancellation and
  consent are checked before and after the network call.

## Why this is not promoted yet

The private benchmark shows detector misses/partial assignments, so a page
proposal route can test recall. It does not prove box ownership, OCR quality,
translation quality or lettering safety. It also adds a full-image API request
and latency, so it requires a separate cost/latency measurement and reviewer
consent. The default remains local PP-OCRv5 until a paired held-out run shows
coverage gain without overmerge, source loss or protected-art changes.

## Verification in this change

- Consent and no-network warmup tests pass.
- Resized-coordinate mapping and review-only flags are tested.
- Full Python suite: `1327 passed, 1 skipped`.
- TypeScript suite: `59 passed`; typecheck and extension build pass.

No private image was uploaded and no paid request was made by this change.

The pinned PaddleOCR-VL-for-Manga comparator was also audited without loading
weights. Its processor/checkpoint preflight passed, but the machine had only
about 1.3 GiB available RAM; its isolated runner correctly refuses FP32
inference below 7 GiB. No forced load or crash was attempted.
