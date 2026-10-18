# Cloud-first desktop test bundle

Cloud-first means **cloud translation**, with the existing pinned local detector
and manga-ocr still supplied. It does not mean full-page cloud vision is proven,
zero local processing, or commercial manga quality.

## Build

```powershell
.\.venv\Scripts\python.exe scripts/package.py --mode portable --profile cloud-first
```

The portable default is now `cloud-first`; `--profile offline` retains the full
local bundle. The cloud-first output is `dist/portable-cloud-first/MangaLiveHost`;
the offline output remains `dist/portable/MangaLiveHost`. Keep the **whole folder**,
including `_internal`, not just the executable.

Both builds run all Python tests and `npm run check` before freezing. Each build
uses its own temporary pytest tree under `build`, not an old shared Windows
pytest cache. No old test/cache tree is deleted to force a pass.

Cloud-first stages only the checksum-verified `ocr` and `detector` model sections.
It does not require/copy local translation/summary GGUFs or the llama.cpp archive.
The inventory rejects leftover `models/translation`, `models/summarizer` or
`runtime` assets rather than silently adding them back to this bundle.
Existing portable markers without a profile retain their offline requirements.

This removes **3,972,066,240 bytes of the two default GGUF files** from the model
payload, plus llama.cpp assets; it is not a measured RAM or runtime improvement.
Python/Paddle/Torch dependencies are still included and can be large.

## Internal tester setup

1. Receive the verified companion folder and `dist/extension` from the same build.
2. Keep the companion in a stable local folder. Load the unpacked extension in
   Edge or Chrome and copy its actual extension ID; do not assume another
   tester has the same ID.
3. Run `Install companion.exe`, choose the correct browser and extension ID,
   then use **Kiểm tra & kết nối**. This writes per-user Native Messaging
   registration; installation does not start translation or call a provider.
4. Open extension settings. Choose BYOK/provider, store **your own** key in
   Windows Vault and explicitly consent to text/context transmission.
5. Leave image OCR off unless separately consenting to image transmission and
   its extra cost. Saving key/settings alone must not initiate translation.
6. Confirm the story and chapter, then start translation. Try original view,
   scrolling, retry and revisiting cached pages.

Never distribute an existing `native-config.json`, reader memory/settings, Vault
credentials, private images, QA reports or a shared API key. `write_checksums`
rejects unexpected root files; a registered folder is not a clean release folder.
The checksum index detects corruption, **not publisher authenticity**. This is an
unsigned internal build, not a signed store release or accepted clean-Windows demo.

Offline remains network-free. This profile intentionally lacks local translation
and summary models; selecting offline cannot silently switch to cloud or download
them. Use the complete offline bundle when local translation is needed later.

## Acceptance still required

Do not call a successful freeze or isolated handshake a repaired personal Edge
profile. Require the actual failing profile, two clean Windows environments,
authored four-bubble flow and at least two real pages with known failures.
No new API budget is granted by building or installing this folder.
