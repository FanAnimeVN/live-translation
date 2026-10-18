# Edge companion: current differential, 2026-10-16

This is a diagnosis checkpoint, **not a personal-profile repair acceptance**.
No registry, policy, security setting, reader data or model setting was changed.
No inference or paid API request was made.

## Fresh reader evidence

The personal Edge diagnostic still reports `NATIVE_HOST_NOT_FOUND` for
`vn.mangalive.companion`, extension `epcjjhbilmmmbojldhnfblgmgiamajpl`,
loaded extension build **`0.1.0-dev.beea32c92a47`**, confirmed after reload.
At that observation it matched the on-disk manifest and successful isolated tests.
Stale build is **not** an explanation of that failure. The subsequent desktop UI
build is `0.1.0-dev.ae423bfce5e4`; there is no new personal-profile observation for it.
Personal-profile repair is still unaccepted.

## Checks actually run

1. `scripts/native_smoke.py --launcher --handshake-only --verify-runtime`
   passed with an isolated temporary configuration and framed hello. The
   development executable can start the current source package. No OCR/LLM ran.
2. `node scripts/probe_native_discovery.mjs --extension-id epcjjhbilmmmbojldhnfblgmgiamajpl`
   failed in the restricted sandbox with the exact NOT_FOUND message. The same
   command in the real Windows account passed: isolated Edge found the actual
   registered host and received the expected framed `PROFILE` rejection before
   hello. This tests discovery/launch without initializing story storage or
   querying the Vault. It does not drive the personal browser.
3. Actual HKCU Edge NativeMessagingHosts values in both Registry32 and Registry64
   point to `D:\Projects\Live translation\dist\windows\vn.mangalive.companion.json`.
   Manifest/config paths exist and the exact extension origin is allowed.
4. The real-account diagnostic process is **not Administrator**. All 23 observed
   Edge processes have the same Windows owner as that diagnostic process, and
   use the installed Edge executable also used by the probe. No personal tabs,
   command lines, browser preferences, profile storage or browser APIs were read.
5. Targeted HKCU/HKLM Windows policy checks found no NativeMessagingUserLevelHosts,
   NativeMessagingBlocklist or NativeMessagingAllowlist values/list entries.
   This does not certify absence of every possible profile/cloud policy.
6. `probe_native_discovery.mjs --bridge` passed both headless and headed in a
   disposable profile, using the production Options/NativeBridge rather than
   only the raw pre-hello transport: `state=ready`, `failure=NONE`, engines cold,
   package `pkg-sha256:f335d0723b4f6a6e97e3c1d6c5440c11666db6c7501600b7472bd7aae0980f1f`.
   Library/settings navigation and save passed desktop/mobile with no inference.
7. A targeted Windows token check found both the diagnostic process and the
   sole observed Edge browser-root process **not elevated**. It did not read
   command lines, tabs or browser profile files. Elevation mismatch is not
   supported by this observation.
8. The final desktop build `0.1.0-dev.ae423bfce5e4` again passed the real installed
   host with production bridge/Options in a disposable Edge profile: `state=ready`,
   `failure=NONE`, engines cold, unchanged runtime package hash. No API/model call,
   Registry change or personal-profile attachment. This does not fix the reader's
   separate profile.

These results argue against a globally missing executable, missing per-user
registration, an administrator-only successful probe or a different Windows
account. They do **not** identify the remaining personal-profile cause.

## Next discriminating observation

Retain the matching-build failure. The reader authorized observation of the
failing personal Options page and `edge://version` only. Computer Use then stopped
because it could not verify the allowed current URL, before those diagnostic pages
were inspected. Personal computer control ended; do not retry that stopped session
or bypass its URL guard with CDP/profile files. Equivalent reader-provided diagnostic
evidence or an appropriately verified future session is still needed before changing
installation behavior.
An isolated-profile success is not personal acceptance. Do not reinstall blindly,
reset storage, change security/policy settings or restart the reader's browser
without authority and attention to unsaved work.

## Distinct live-pipeline result

The same source build completed real detector -> cloud crop OCR -> cloud text
translation -> overlay in an isolated Edge/QA-host installation. Four authored
balloons completed cold 25.624s, warm/new-page 6.196s, cached revisit 0.319s by
the harness's 250ms completion polling. Native durations were 25.221s/5.893s/
2.420ms respectively. This was four real cloud requests, not the read-only
discovery probe. It does not fix or certify the personal-profile lookup failure.

The demo HTTP server is unrelated to host discovery. Edge itself launches the
native host for `runtime.connectNative`; starting a localhost image server does
not register or repair that host. [Microsoft Native Messaging protocol and
debugging](https://learn.microsoft.com/en-us/microsoft-edge/extensions/developer-guide/native-messaging#native-messaging-protocol).

## Personal Edge retest after explicit restart — 2026-10-16

The reader authorized one `edge://restart` after saving work. Computer Use
verified the restored Edge window, reloaded the unpacked extension from the
project folder, and opened Options again. The page still reported
`NATIVE_HOST_NOT_FOUND` on build `0.1.0-dev.6d51b1c6f62b`; an explicit
Reconnect remained in the same failure state. This rules out a merely stale
Options tab, stale service worker, or a missing browser-process restart, but it
does not identify the remaining Edge profile-specific lookup difference.

The approved read-only account check still finds both HKCU registry views at
the documented Edge key, and both resolve to the same valid 283-byte manifest;
the manifest and `MangaLiveHost.exe` are readable. The development launcher
also passed `native_smoke.py --launcher --handshake-only --verify-runtime`
with a temporary profile and no inference/API call. The exact personal
failure therefore remains open; do not claim that the host is repaired or
ask the reader to reset profile data. Source-level lookup branches and the
next non-mutating differential are recorded in
`native-lookup-source-differential-20261016.md`.
