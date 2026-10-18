# Private context backups

SQLite remains authoritative. Markdown is a short, cutoff-filtered view for reading/model input; the schema-1 JSON backup retains the full private history, profile and reading progress. Images, API keys, page pixels and short-lived translation caches are not exported.

## Transfer and snapshot contract

- `memory.export.page` sends up to 128 KiB of records per reply with framing headroom. A cursor binds story ID, semantic version, profile/progress snapshot hash and optional reading cutoff. Reading progress can invalidate an export cursor without changing the translation context version.
- The client rejects duplicate IDs, changing snapshots, repeated cursors, oversized replies and no-progress replies. A full export never silently returns a partial file. The library uses the selected chapter/page cutoff; full-history export separately warns about spoilers and private data.
- `context.begin/chunk/commit/cancel` imports UTF-8 JSON in bounded RAM chunks. The host verifies offset, size and SHA-256 before one atomic database import. Aggregate reservations are limited to 16 MiB and expire after 120 seconds. These operations are restricted to extension-owned UI, not webpage content scripts.

## Additive import behavior

New stories restore title, genre, identity aliases/metadata, summaries, temporal facts and resume progress. An existing story keeps its title, nonempty genre/metadata and current resume position; compatible aliases are merged and the furthest-read chapter can increase. Conflicting identity IDs are rejected.

Import is idempotent. Original record IDs are retained where possible and namespaced on collisions with another story. Equivalent records do not duplicate or increment context version; nested import provenance is normalized rather than growing on every round trip. Flags accept only booleans or SQLite 0/1, never strings such as `"false"`. Original text and summary kind are preserved.

Group dependencies are resolved before writing their parent, including reversed export order, equivalent children with different IDs and foreign-story ID collisions. Links must resolve to complete, valid summaries in the same story, inside the parent's chapter/page range. Missing, cyclic, duplicate, partial or future links abort the whole import. Broken legacy groups remain available in a full backup for repair but are excluded from translation context and cutoff-filtered library exports.

`complete` means source coverage, not that an AI paraphrase has been semantically checked. Dialogue-generated groups are expanded to their validated original child evidence for translation prompts; a group's own added quotes, speaker IDs and paraphrase do not override those children. Child cutoffs remain unchanged. Explicit reader-supplied/confirmed group text remains a reader assertion. Expansion is deduplicated and uses a per-snapshot lookup cache, so older evidence can remain reachable through a recent group without repeating shared leaves in the prompt. The final context byte budget still applies.

Temporally eligible, contract-validated names and canonical term aliases can also retrieve older original dialogue evidence outside the latest 20 candidates. Lookup uses at most six literal Japanese aliases and 24 additional summary candidates; the prompt budget and same-page/future exclusions still apply. Alias versions introduced later are not used at earlier cutoffs. Malformed embedded name/term records are retained in the private backup for review but do not drive identity lookup. Malformed dialogue lists are not evidence and cannot crash translation retrieval.

Event facts, reader notes and expanded summary evidence share a relevance-ranked budget. A related original quote is considered before unrelated new notes; equally relevant locked reader assertions keep priority over generated evidence. This prevents a large unrelated note from starving the specific context the current line needs. Ranking never relaxes temporal exclusions or promotes unverified paraphrases into facts.

A new imported fact cannot shadow an existing confirmed reader lock at its applicable cutoff or downgrade its confirmation. Conflicts abort the entire import, leaving existing data unchanged. Intentional changes are made through the library's temporal editor, not by silently overwriting a private backup. Historical reader revisions and spoiler cutoffs remain intact.

## Verification and limits

- Python regression tests cover atomic rejection, metadata/progress round trips, existing reader locks, duplicate imports, ID collisions, stale cursors, incomplete chunks, invalid UTF-8, quota, expiry and offsets.
- The real framed Python host exported/imported a 1.65 MB author-created storage fixture containing 1,000 summaries over 100 chapter markers; each response stayed below 160 KB, and cutoff 20 returned exactly 200 eligible summaries. This is **storage/protocol evidence**, not proof that a model correctly summarized 100 chapters.
- Rendered library QA uses an independent headless Edge with mocked native replies. It covers large UTF-8 import, local search, 10-record incremental display, expandable notes, first-viewport 390 px layout and stale response cancellation. This does not prove personal Edge Native Messaging registration or manga translation quality.
- Large context backup transfer is not the latency-critical translation retrieval path. The 16 MB cap is an MVP transfer limit, not a claim that all 100-chapter histories will fit or summarize reliably.
