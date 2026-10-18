# Directed waiting-role fix — 2026-10-15

The local semantic replay exposed a concrete pronoun reversal in the sibling
fixture: `わかった。待ってるね。` was rendered as `Chị sẽ chờ em` while the
confirmed pair said that the younger speaker (`em`) was waiting for the older
listener (`chị`).

The fix is intentionally evidence-first and narrow:

- only a confirmed speaker/listener pair is eligible;
- the Japanese source must be the short implicit-subject `待ってる`/`待っています`
  reply, without an explicit third-person subject, quoted narration, or an
  imperative `待ってて` request;
- only the reversed Vietnamese shape `[listener] … chờ/đợi [speaker]`, or a
  generic first-person subject such as `Tôi sẽ chờ cô ấy`, is rejected;
- unknown roles, explicit reader locks, and other Japanese clauses remain
  untouched and available for ordinary model review.

The provider retries only the failed region once. The repair instruction is
present in full, compact and focused prompt adapters. The prompt cache version
is now `ja-vi-v22-directed-wait-no-stack`.

Evidence from this checkout:

- targeted linguistics/provider tests: 2 passed;
- full Python suite: 1038 passed, 1 skipped;
- TypeScript: 51 passed; typecheck and extension build passed;
- local guided sibling replay: final item `Được rồi. Em sẽ chờ chị.` and all
  narrow checks passed. The small local compact-prompt replay still failed
  closed on a persistent model-output error after its one bounded retry; that
  is evidence of the local model limitation, not permission to show the bad
  text and not a general translation-quality score.

