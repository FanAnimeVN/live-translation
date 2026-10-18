# Native host registration repair — 2026-10-15

## Reported state

The reader supplied `NATIVE_HOST_NOT_FOUND` for Edge, host
`vn.mangalive.companion`, extension `epcjjhbilmmmbojldhnfblgmgiamajpl`,
and loaded build `0.1.0-dev.60d42114b11f`. The on-disk extension is
`0.1.0-dev.d07a2886be4a`. These are different builds; neither a successful
source build nor a disposable browser test proves that the personal profile
has reloaded the new one.

## Reproduced installer defect

`REGISTRY` already ends in `NativeMessagingHosts`. The installer appended
that component again and wrote a valid but undiscoverable nested key.
Edge's documented per-user location is
`Software\Microsoft\Edge\NativeMessagingHosts\vn.mangalive.companion`.
See [Microsoft's native-host registration documentation](https://learn.microsoft.com/en-us/microsoft-edge/extensions/developer-guide/native-messaging#step-3-copy-the-native-messaging-host-manifest-file-to-your-system).

The original tests checked that a value was written, but not its exact path.
An existing correct registration also masked the defect in browser probes.
New fixtures start with an empty registry double and assert the independently
specified Edge/Chrome paths in default, 32-bit and 64-bit views. No production
registry is deleted to simulate a fresh install.

Red command:

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/python/test_install_native.py -q
```

The new cases failed before the fix: 3 failed, 16 passed. Removing the duplicate
path component made the registration and QA-registration suite pass: 27 tests.

## Applied and verified

- Ran the corrected source installer for Edge and the exact installed ID in
  the real Windows account, not the sandbox account. Read-back confirms the
  correct manifest in both explicit registry views.
- Disposable Edge, using the real production host registration and the same
  extension ID/build, received the expected framed `PROFILE` rejection to a
  status request sent before `hello`. This verifies discovery and launch without
  initializing a reader profile, querying the Vault, loading a model or cloud.
- The packaged development launcher passed `native_smoke.py --launcher
  --handshake-only` with a temporary profile. It reported prompt v21, OCR
  local-v3, layout v16 and scope v4. This is not OCR/translation quality proof.
- Full Python suite: 989 passed, 1 skipped. Typecheck, 51 TypeScript tests and
  extension build passed. No OCR/grouping/lettering quality gates were changed.
- Built `dist/windows/Install companion.exe` with the corrected installer.
  GUI runtime self-test passed, with no registry or reader-data operation.
  SHA256: `c2af951182de8fc4948d92579fa3f35fbb0f10f6cebbc1c5a6a630a0587e2945`.

During packaging, PyInstaller in the sandbox initially omitted tkinter after
Tcl initialization failed, yet exited successfully. The same Tcl runtime
initialized successfully under the real user account. `package.freeze` now
checks Tcl initialization and Tcl/Tk data before overwriting an installer;
the corrected rebuild used the working account and included the tkinter hook.
The frozen installer's `--self-test` initializes/withdraws/destroys its GUI
without registration, models or reader storage. The new packaging fixtures
were red before the preflight and green afterward.

Only the development installer was rebuilt. Previously staged portable bundles
are not refreshed or certified by this change.

## Personal-profile verification still required

Latest read-only probe reproduced `NATIVE_HOST_NOT_FOUND` when run under the
restricted sandbox because its HKCU registry view is different. Re-running
the existing per-user installer with the approved Windows account succeeded;
the same-account isolated Edge probe then returned the expected `PROFILE`
response with `idMatches: true`. This verifies the registration/path for that
account without loading a model, opening Vault or calling cloud APIs. The
restricted shell cannot read that account's HKCU key, so it must not be used as
evidence about the user's visible Edge profile.

Computer Use found no open Edge window and launched the existing browser. Its
subsequent window-access approval timed out; no extension UI action was taken.
Do not treat the isolated probe as a successful personal-profile reconnect.

In `edge://extensions`, Reload the extension loaded from
`D:\Projects\Live translation\dist\extension`. Close the old Settings tab,
then open Settings again and reconnect. That repair's build ended in
`d07a2886be4a`; later builds are described below. If it still fails, collect a fresh public connection diagnostic;
do not reset the reader profile, re-enter keys, loosen permissions or change
antivirus/policies.

## Follow-up: distinguish development source from a frozen host

The registered `dist/windows/MangaLiveHost.exe` is a development launcher.
Its `native-config.json` points to this project's `.venv` and `companion/entry.py`.
Its executable modification time therefore does not identify the Python logic
used by a newly started process. A direct framed handshake returned prompt v22
and the current layout/scope versions without rebuilding that launcher.
This corrects the earlier assumption that every Python change requires freezing
the currently registered development host again.

`hello` and `status` now expose `runtimeBuild`, a SHA-256 identity of the
first-party `manga_live` Python package. A development process captures its
source snapshot once at host-module import, not on every status call. A frozen
host uses a build-time record embedded under `manga_live/_runtime_build.json`;
it cannot borrow an identity from a neighboring checkout. The freezer fails
verification if package sources change during freezing. This metadata is not
a signature, loaded-bytecode attestation, dependency/weight checksum, or
OCR/translation quality certificate. Restart after source edits; do not edit
the source while a verification/build is in progress.

The Options page shows this identity under **Kết nối và phiên bản runtime**.
Legacy hosts remain usable but explicitly show that they have not reported a
runtime identity. Invalid/unbounded identity values fail status validation.
Opening this section does not request inference, change consent or settings,
or charge an API. The extension build is separate, displayed in the footer.

Read-only, isolated-profile comparison against current source:

```powershell
.\.venv\Scripts\python.exe -B scripts/native_smoke.py --launcher --handshake-only --verify-runtime
```

The command was red before the status field existed and green afterward.
The actual staged old portable executable was also tested with
`--host-executable dist/portable/MangaLiveHost/MangaLiveHost.exe` instead of
`--launcher`: it was rejected as old/different/unidentified before inference.
The verifier requires `--handshake-only`; it does not permit a paid or local
inference operation under that flag. Both probes used new temporary profiles,
not the reader's keys, story memory, or settings. They do not prove discovery
or reconnect in the personal Edge profile.

No portable bundle was rebuilt or certified. The runtime-record packaging
tests verify freezer arguments and data records, not a newly frozen host's
real execution. The previous portable remains out of date. Source/launcher
verification and mocked-transport Options QA do not satisfy the outstanding
real manga, personal-browser, translation-quality or latency acceptance gates.
