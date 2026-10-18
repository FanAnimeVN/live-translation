# Edge Native Messaging discovery — 2026-10-14

Latest follow-up: [fresh-install path regression and verified repair, 2026-10-15](native-host-fix-20261015.md).
The earlier production probe below did not catch the installer's nested-path
bug because a correct registration already existed. Fresh-registry regression
fixtures now cover that gap.

## Current evidence

- Personal browser is Microsoft Edge Stable `155.0.4283.45`; extension ID is `epcjjhbilmmmbojldhnfblgmgiamajpl`. The rebuilt unpacked extension is `0.1.0-dev.d07a2886be4a`.
- The host key was re-registered for the current Windows user in all three Python registry views (default, 32-bit and 64-bit) and points to the same manifest:
  `D:\Projects\Live translation\dist\windows\vn.mangalive.companion.json`.
- The manifest is valid JSON, names `vn.mangalive.companion`, points to the existing `MangaLiveHost.exe`, and allows the exact extension origin.
- A disposable Edge profile launched with the same unpacked extension ID and the real user-level registration returned the expected framed `PROFILE` rejection before `hello`. It did not load models, read the Vault, or initialize a reader profile.
- The earlier personal-profile `NATIVE_HOST_NOT_FOUND` JSON was captured before this re-registration/rebuild. A disposable Edge profile using the rebuilt extension and the real user-level registration now returns the expected framed `PROFILE` rejection before `hello` (pass); the personal profile still needs an Edge process restart and extension reload for final verification.
- The user checked `edge://policy`: no Edge policies are set, including no visible native-messaging policy. This is evidence against a visible machine/profile policy, not proof that every account/cloud policy path is absent.

## Relevant primary documentation

Microsoft documents that Edge searches the CurrentUser Edge registry before LocalMachine, checks 32-bit before 64-bit, and reads the manifest path from the registry: [Native messaging — registry search order](https://learn.microsoft.com/en-us/microsoft-edge/extensions/developer-guide/native-messaging#step-3-copy-the-native-messaging-host-manifest-file-to-your-system).

The same documentation lists the NOT_FOUND family of checks (host name, manifest location/format, and executable path) and distinguishes an `allowed_origins` problem as forbidden: [Debugging native messaging](https://learn.microsoft.com/en-us/microsoft-edge/extensions/developer-guide/native-messaging#debugging-native-messaging).

Edge's `NativeMessagingUserLevelHosts` policy is enabled when unset and disables user-level hosts only when explicitly disabled. The policy is dynamic and per profile: [NativeMessagingUserLevelHosts](https://learn.microsoft.com/en-us/deployedge/microsoft-edge-policies/NativeMessagingUserLevelHosts).

## Safe next differential

Because registration, manifest, executable existence, exact origin, and visible policy are checked, refresh the **Edge process** once (`edge://restart`, or close all Edge windows and reopen the same profile), then reload the unpacked extension and open Settings again. This tests process-level host discovery/cache without changing registry, profile storage, keys, or security settings. If it still fails, the next useful artifact is the service-worker error output from `edge://extensions` after one explicit reconnect; do not reset the profile or install a second host.

This note does not claim that the personal profile is fixed or that the extension can be shipped yet.

## Separate CSP regression, reproduced and fixed

The next user screenshot showed an options-page DevTools issue at `ui.js`: dynamic evaluation was blocked by `script-src 'self'`. It is not evidence of a service-worker discovery error or a reason to weaken CSP.

The production-bundle connection QA was made red-capable by serving the options page under the manifest's strict CSP and recording `securitypolicyviolation`, including caught capability probes. All six scenarios failed with `blockedURI=eval` before the fix. Local Zod source (`4.6.6`) identifies its object-schema evaluation probe and its `jitless` setting.

`shared/contracts.ts` now calls `z.config({ jitless: true })` before any schema construction. Schema validation and refinements stay enabled in each extension realm; the MV3 CSP is unchanged. The built-on-disk marker is now **`0.1.0-dev.d07a2886be4a`**; this is not yet proof that the personal Edge profile has reloaded it.

Validation after the edit: typecheck, 51 TypeScript tests and build pass; all six strict-CSP connection scenarios pass with zero CSP violations; options/library QA and content-script QA pass on isolated Edge. The latter cover desktop/mobile, source restoration, scroll/resize, and stale replies using authored fixtures and mocked transport. They do not prove personal Native Messaging, real OCR/translation accuracy, or real-manga lettering fidelity. The development native registration was re-written only for the exact extension ID and manifest path; no key, memory, or CSP permission was changed.
