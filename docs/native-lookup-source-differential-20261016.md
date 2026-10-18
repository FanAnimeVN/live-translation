# Native Messaging lookup differential (2026-10-16)

## Scope and evidence

This note is a source-backed differential for the personal Edge profile reporting
`Specified native messaging host not found.` for `vn.mangalive.companion`, while an
isolated Edge profile can connect. It does **not** inspect browser profile data, read
logs, change the registry, or launch the host. The current observations are that
the executable/channel and Windows user are the same, no Edge policies are set, and
the expected per-user Edge registry entries, manifest path, host name and extension
origin have already been checked. Those observations are local evidence, not a
claim that the personal profile is fixed.

## What the browser error actually distinguishes

Chromium's native-messaging documentation separates these failures:

Chromium exposes distinct error constants (`kNotFoundError`, `kForbiddenError`,
`kFailedToStartError`, `kNativeHostExited`, `kHostInputOutputError`) in its public
native-host interface:
<https://chromium.googlesource.com/chromium/src/+/HEAD/extensions/browser/api/messaging/native_message_host.h>.
The current launch-context/Windows implementation bodies were not retrievable in
this research session. The branch descriptions below therefore describe the
official troubleshooting table, **not a verified line-by-line trace of Edge 155**.

* **`Specified native messaging host not found.`** is the manifest lookup/validation
  branch. The documented checks are the host name spelling, manifest directory and
  filename, valid JSON and required manifest values, and whether the `path` file
  exists. See the Chromium documentation's error table:
  <https://chromium.googlesource.com/chromium/src/+/main/chrome/common/extensions/docs/templates/articles/nativeMessaging.html#native-messaging-debugging>
* **`Native host <name> is not registered. (Windows-only)`** is separately listed in
  the documentation for a missing Windows registry registration. This table does
  not prove that current Edge exposes that internal detail directly to the
  extension: several lookup failures can be surfaced as the generic not-found
  message. The literal alone cannot identify whether the selected key, manifest
  read/parse, or executable existence check failed.
* **`Access to the specified native messaging host is forbidden.`** is the
  `allowed_origins` check, and **`Native host has exited`**/communication errors
  happen after launch. They should not be conflated with lookup failure.

Microsoft's Edge documentation states the same branches and explicitly says that
the browser validates the host manifest, then checks its `name`, `path`, `type` and
`allowed_origins` fields. It also states that a Windows `path` may be relative to
the manifest directory and that the host starts with the directory containing the
binary as its current directory:
<https://learn.microsoft.com/en-us/microsoft-edge/extensions/developer-guide/native-messaging#step-2-create-your-native-messaging-host-manifest-file>
<https://learn.microsoft.com/en-us/microsoft-edge/extensions/developer-guide/native-messaging#debugging-native-messaging>

## Registry selection is an important, falsifiable differential

Edge searches user scope before machine scope and searches 32-bit before 64-bit.
The first matching registry location wins; if a matching Microsoft Edge key is
found, Edge does not continue to later Chromium/Chrome locations. On a 64-bit
machine, `HKCU\\SOFTWARE\\WOW6432Node` is not searched. These rules are documented
with the complete search order here:
<https://learn.microsoft.com/en-us/microsoft-edge/extensions/developer-guide/native-messaging#step-3-copy-the-native-messaging-host-manifest-file-to-your-system>

Consequently, “both HKCU views contain a good manifest” is not by itself a proof
that the personal profile reads the same bytes: the next safe check should identify
the **first registry location selected by Edge**, read that exact default value,
and validate that exact file (UTF-8 JSON, `name`, `type: stdio`, absolute or
manifest-relative `path`, existing file, and the personal extension ID in
`allowed_origins`). Do this with the existing read-only diagnostic, without
rewriting either key. A stale first 32-bit value, a path that exists only through
a different current directory, or a manifest read/parse failure remains consistent
with the exact browser message even when a later 64-bit entry is correct.

## Launch-mode policy is a later differential, not the first fix

Microsoft Edge has a `NativeHostsExecutablesLaunchDirectly` policy (Windows Edge
121+). When enabled, Edge launches executable hosts directly; when disabled it
uses `cmd.exe`; when unset it chooses during a progressive rollout. The policy
requires an Edge restart and is per profile. This policy changes **launch behavior**,
so it is relevant only after the manifest has been found and validated; it is not a
reason to rewrite registration or lower security. Source:
<https://learn.microsoft.com/en-us/deployedge/microsoft-edge-browser-policies/nativehostsexecutableslaunchdirectly>

Two other first-party policies can block an otherwise valid registration:
`NativeMessagingUserLevelHosts` must not be disabled for an HKCU-only install,
and `NativeMessagingBlocklist` can deny a host (with `NativeMessagingAllowlist`
providing exceptions). Microsoft documents that user-level hosts are allowed by
default when the former is unset, and that all hosts are loaded when the blocklist
is unset:
<https://learn.microsoft.com/en-us/deployedge/microsoft-edge-policies/nativemessaginguserlevelhosts>
<https://learn.microsoft.com/en-us/deployedge/microsoft-edge-policies/nativemessagingblocklist>
<https://learn.microsoft.com/en-us/deployedge/microsoft-edge-browser-policies/nativemessagingallowlist>

The reported `edge://policy` page showed no policies, so this differential is
currently ruled out by observation; it should remain in an installer diagnostic so
that a managed tester receives an actionable result instead of a generic lookup
error.

## Safe next differential (in order)

1. Use the existing diagnostic to report the selected registry view/default value,
   resolved manifest path, file existence/readability, JSON parse result and the
   exact host `name`/`type`/`path`/`allowed_origins` checks. Do not report “registry
   present” as “manifest accepted”.
2. Compare the bytes and resolved path selected in the personal profile with the
   isolated profile. Keep the comparison text-only; do not inspect unrelated
   browser/profile data or send the manifest/key to a cloud provider.
3. If the manifest is accepted in both, record a fresh Edge restart and then use
   Edge's documented native-messaging error log facility (`--enable-logging`) to
   distinguish launch failure from lookup failure. The Microsoft guidance notes
   that native-messaging startup/protocol failures are written to Edge's error log:
   <https://learn.microsoft.com/en-us/microsoft-edge/extensions/developer-guide/native-messaging#debugging-native-messaging>
4. Only if the log shows a launch-mode failure should the existing installer/diagnostic
   evaluate the direct-launch policy. Do not alter policy, registry, security
   software, or the user's profile automatically.

## Non-conclusions

The sources do not establish that a browser restart repairs this case, nor that the
HTTP demo server is involved. They also do not justify silently re-registering the
host, changing `allowed_origins`, or shipping a second manifest. The current
`NATIVE_HOST_NOT_FOUND` is therefore still an unresolved personal-profile lookup/
validation symptom until the selected manifest bytes and Edge diagnostic log branch
are observed. Do not claim that the browser actually selected a key merely because
an independent installer diagnostic can read it.
