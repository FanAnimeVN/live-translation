import type { NameKind, PageNotes, ReadingPosition, RegionTranslation } from "./types";

export type EntryStatus = "auto" | "confirmed" | "locked" | "rejected";
/** Where a remembered fact came from. Reader > page evidence > summary > metadata. */
export type Source = "reader" | "page" | "summary" | "metadata";

export interface Evidence {
  pageId: string;
  regionId: string;
  pos: ReadingPosition;
}

/** A name or term; characters carry a small card used for pronoun and register choices. */
export interface MemoryEntity {
  ja: string;
  vi: string;
  kind: NameKind;
  status: EntryStatus;
  note?: string;
  knownFrom: ReadingPosition;
  evidence: Evidence[];
  history: Array<{ at: string; vi: string; status: EntryStatus }>;
  gender?: "female" | "male" | "unknown";
  /** main / supporting / background, or a short descriptor ("cat", "teacher"). */
  role?: string;
  /** Self-reference and speaking style, e.g. "あたし; cheerful, childish". */
  speech?: string;
  /** Short relationship facts known so far. */
  relations?: string[];
  /** Official romanization from metadata (spelling only). */
  officialName?: string;
  source?: Source;
  lastSeen?: ReadingPosition;
  seen?: number;
}

/** Directed address rule: how `from` speaks to `to`. Never derive the reverse. */
export interface MemoryAddress {
  from: string;
  to: string;
  call?: string;
  selfVi?: string;
  addressVi?: string;
  status: EntryStatus;
  knownFrom: ReadingPosition;
  evidence: Evidence[];
  source?: Source;
  /** Times the same pair was observed with these terms. */
  count?: number;
}

export interface RecentLine {
  pageId: string;
  regionId: string;
  speaker: string;
  to?: string;
  ja: string;
  vi: string;
  pos: ReadingPosition;
}

export interface SeriesProfile {
  genres: string[];
  tone?: string;
  setting?: string;
  /** Vietnamese register guidance for this story (built once, then reused). */
  register?: string;
  /** Non-spoiler premise. */
  synopsis?: string;
  source: Source;
}

export interface StoryEvent {
  text: string;
  pos: ReadingPosition;
  evidence: Evidence[];
}

export interface StorySummary {
  /** Story so far, written only from pages up to `upTo`. */
  text: string;
  upTo: ReadingPosition;
  events: StoryEvent[];
  model?: string;
  updatedAt: string;
}

/**
 * One background summary, kept for good (the archive): what the newly read dialogue
 * added, and the rolling story at that point. Requests only get a compact selection
 * that fits a token budget; the archive keeps every original, for recaps, re-reading
 * earlier chapters and comparing summary models.
 */
export interface SummaryRecord {
  from: ReadingPosition;
  upTo: ReadingPosition;
  /** What happened in the lines this update read (Vietnamese, short). */
  segment: string;
  /** The rolling story so far after this update (Vietnamese, about 120 words at most). */
  story: string;
  events: StoryEvent[];
  model: string;
  at: string;
}

export interface MetaCharacter {
  native: string;
  full: string;
  alternative: string[];
  gender?: string;
  role?: string;
  /** Spoiler-stripped, short. */
  description?: string;
  /** Hints prepared from metadata, copied to the cast card once the character is seen. */
  speech?: string;
  relations?: string[];
}

export interface SeriesMetadata {
  source: "anilist";
  id: number;
  title: string;
  url?: string;
  characters: MetaCharacter[];
  fetchedAt: string;
}

export interface SeriesMemory {
  seriesId: string;
  title: string;
  entities: MemoryEntity[];
  address: MemoryAddress[];
  recent: RecentLine[];
  /** Reader-written recap or character list (cold start). */
  readerNotes?: string;
  profile?: SeriesProfile;
  summary?: StorySummary;
  /** Every background summary ever made, oldest first (never trimmed into the prompt as a whole). */
  archive?: SummaryRecord[];
  /** Dialogue read since the last background summary (bounded). */
  pending?: RecentLine[];
  /** Confirmed external metadata; its characters only surface once seen in the story. */
  metadata?: SeriesMetadata;
  updatedAt: string;
}

export function emptyMemory(seriesId: string, title: string): SeriesMemory {
  return { seriesId, title, entities: [], address: [], recent: [], updatedAt: new Date().toISOString() };
}

export const atOrBefore = (a: ReadingPosition, b: ReadingPosition) =>
  a.chapter < b.chapter || (a.chapter === b.chapter && a.page <= b.page);

const RECENT_LIMIT = 12;
const PENDING_LIMIT = 160;
const normalizeKey = (s: string) => s.normalize("NFKC").replace(/[\s・·=＝]/g, "");

/** Metadata character whose native name matches a name seen in the story. */
export function matchMetaCharacter(meta: SeriesMetadata | undefined, ja: string): MetaCharacter | undefined {
  if (!meta) return undefined;
  const k = normalizeKey(ja);
  if (k.length < 2) return undefined;
  return (
    meta.characters.find((c) => normalizeKey(c.native) === k || c.alternative.some((a) => normalizeKey(a) === k)) ??
    meta.characters.find((c) => {
      const n = normalizeKey(c.native);
      return n.length >= 2 && (n.includes(k) || k.includes(n)) && Math.min(n.length, k.length) >= 2;
    })
  );
}

/**
 * Merge a page's notes and dialogue into the series memory. New names become
 * "auto" proposals (enriched from confirmed metadata when the name matches); existing
 * entries keep their rendering so names stay stable; reader-confirmed/locked entries
 * are never overwritten.
 */
export function mergePage(
  mem: SeriesMemory,
  pageId: string,
  pos: ReadingPosition,
  notes: PageNotes,
  translations: RegionTranslation[],
): { memory: SeriesMemory; proposals: MemoryEntity[] } {
  const now = new Date().toISOString();
  const entities = mem.entities.map((e) => ({ ...e, evidence: [...e.evidence] }));
  const proposals: MemoryEntity[] = [];
  for (const n of notes.names) {
    const key = normalizeKey(n.ja);
    const ev: Evidence = { pageId, regionId: n.evidence, pos };
    const existing = entities.find((e) => normalizeKey(e.ja) === key);
    if (existing) {
      if (!existing.evidence.some((x) => x.pageId === pageId && x.regionId === ev.regionId)) existing.evidence.push(ev);
      if (atOrBefore(pos, existing.knownFrom)) existing.knownFrom = pos;
      if (!existing.lastSeen || atOrBefore(existing.lastSeen, pos)) existing.lastSeen = pos;
      existing.seen = (existing.seen ?? 1) + 1;
      continue;
    }
    const meta = n.kind === "character" ? matchMetaCharacter(mem.metadata, n.ja) : undefined;
    const entity: MemoryEntity = {
      ja: n.ja,
      vi: n.vi,
      kind: n.kind,
      status: "auto",
      note: n.note,
      knownFrom: pos,
      evidence: [ev],
      history: [{ at: now, vi: n.vi, status: "auto" }],
      source: "page",
      lastSeen: pos,
      seen: 1,
      ...(meta && {
        gender: meta.gender === "Female" ? "female" : meta.gender === "Male" ? "male" : undefined,
        role: meta.role?.toLowerCase(),
        officialName: meta.full,
        speech: meta.speech,
        relations: meta.relations?.slice(0, 3),
        source: "metadata" as const,
      }),
    };
    entities.push(entity);
    proposals.push(entity);
  }

  const address = mem.address.map((a) => ({ ...a, evidence: [...a.evidence] }));
  for (const a of notes.address) {
    const ev: Evidence = { pageId, regionId: a.evidence, pos };
    const existing = address.find((x) => x.from === a.from && x.to === a.to);
    if (existing) {
      const same = (!a.self_vi || a.self_vi === existing.selfVi) && (!a.address_vi || a.address_vi === existing.addressVi);
      if (existing.status === "auto") {
        existing.call ??= a.call;
        existing.selfVi ??= a.self_vi;
        existing.addressVi ??= a.address_vi;
      }
      if (same) existing.count = (existing.count ?? 1) + 1;
      existing.evidence = [...existing.evidence.slice(-5), ev];
      continue;
    }
    address.push({
      from: a.from,
      to: a.to,
      call: a.call,
      selfVi: a.self_vi,
      addressVi: a.address_vi,
      status: "auto",
      knownFrom: pos,
      evidence: [ev],
      source: "page",
      count: 1,
    });
  }

  const lines: RecentLine[] = translations
    .filter((t) => t.role !== "none" && t.role !== "decorative" && (t.ja || t.vi))
    .sort((a, b) => a.seq - b.seq)
    .map((t) => ({ pageId, regionId: t.id, speaker: t.speaker, to: t.to, ja: t.ja, vi: t.vi, pos }));
  const recent = [...mem.recent.filter((r) => r.pageId !== pageId), ...lines].slice(-RECENT_LIMIT);
  const pending = [...(mem.pending ?? []).filter((r) => r.pageId !== pageId), ...lines].slice(-PENDING_LIMIT);

  const profile =
    mem.profile ??
    (notes.series && notes.series.genres.length
      ? { genres: notes.series.genres, tone: notes.series.tone, setting: notes.series.setting, source: "page" as const }
      : undefined);

  return { memory: { ...mem, entities, address, recent, pending, profile, updatedAt: now }, proposals };
}

export function setEntityStatus(mem: SeriesMemory, ja: string, status: EntryStatus, vi?: string): SeriesMemory {
  const key = normalizeKey(ja);
  const now = new Date().toISOString();
  return {
    ...mem,
    updatedAt: now,
    entities: mem.entities.map((e) =>
      normalizeKey(e.ja) === key
        ? { ...e, status, vi: vi ?? e.vi, source: status === "auto" ? e.source : "reader", history: [...e.history, { at: now, vi: vi ?? e.vi, status }] }
        : e,
    ),
  };
}

/** Background memory update produced by a cheap model from the pending dialogue. */
export interface MemoryUpdate {
  story_so_far?: string;
  /** What the new dialogue added, on its own. */
  segment?: string;
  events?: Array<{ text: string; evidence?: string[] }>;
  characters?: Array<{ name: string; ja?: string; gender?: string; role?: string; speech?: string; relations?: string[] }>;
  address?: Array<{ from: string; to: string; call?: string; self_vi?: string; address_vi?: string; evidence?: string[] }>;
}

/**
 * Apply a background update. Only fills gaps or adds facts: locked/confirmed entries
 * are untouched, nothing is dated after the last page the update read (`upTo`).
 */
export function applyMemoryUpdate(
  mem: SeriesMemory,
  u: MemoryUpdate,
  upTo: ReadingPosition,
  model: string,
  /** Lines that were not part of this update (read while it ran); they stay pending. */
  keepPending: RecentLine[] = [],
): SeriesMemory {
  const now = new Date().toISOString();
  const byPage = new Map((mem.pending ?? []).map((l) => [l.pageId, l.pos]));
  const evidenceOf = (refs: string[] | undefined): Evidence[] =>
    (refs ?? [])
      .map((ref) => {
        const [pageId, regionId] = ref.split(":");
        const pos = byPage.get(pageId);
        return pos ? { pageId, regionId: regionId ?? "", pos } : undefined;
      })
      .filter((e): e is Evidence => !!e)
      .slice(0, 4);

  const entities = mem.entities.map((e) => ({ ...e }));
  for (const c of u.characters ?? []) {
    const e = entities.find(
      (x) => x.kind === "character" && ((c.ja && normalizeKey(x.ja) === normalizeKey(c.ja)) || x.vi.toLowerCase() === c.name.toLowerCase()),
    );
    if (!e || e.status === "locked" || e.status === "confirmed") continue;
    const g = (c.gender ?? "").toLowerCase();
    if ((!e.gender || e.gender === "unknown") && (g === "female" || g === "male")) e.gender = g;
    e.role ??= c.role;
    e.speech ??= c.speech;
    const rel = new Set([...(e.relations ?? []), ...(c.relations ?? []).map((r) => r.trim()).filter(Boolean)]);
    e.relations = [...rel].slice(-4);
  }

  const address = mem.address.map((a) => ({ ...a }));
  for (const a of u.address ?? []) {
    if (!a.from || !a.to || a.from === "unknown" || a.to === "unknown") continue;
    const ex = address.find((x) => x.from === a.from && x.to === a.to);
    if (ex) {
      if (ex.status === "auto") {
        ex.selfVi ??= a.self_vi;
        ex.addressVi ??= a.address_vi;
        ex.call ??= a.call;
      }
      continue;
    }
    const ev = evidenceOf(a.evidence);
    if (!ev.length) continue; // a rule needs evidence from pages already read
    address.push({ from: a.from, to: a.to, call: a.call, selfVi: a.self_vi, addressVi: a.address_vi, status: "auto", knownFrom: ev[0].pos, evidence: ev, source: "summary", count: 1 });
  }

  const fresh: StoryEvent[] = (u.events ?? [])
    .map((e) => {
      const ev = evidenceOf(e.evidence);
      return { text: e.text.trim().slice(0, 200), pos: ev.length ? ev[ev.length - 1].pos : upTo, evidence: ev };
    })
    .filter((e) => e.text && e.evidence.length);
  const events: StoryEvent[] = [...(mem.summary?.events ?? []), ...fresh].slice(-40);

  const story = (u.story_so_far ?? mem.summary?.text ?? "").trim().slice(0, 900);
  const kept = new Set(keepPending.map((l) => `${l.pageId}:${l.regionId}`));
  const covered = (mem.pending ?? []).filter((l) => !kept.has(`${l.pageId}:${l.regionId}`));
  const from = covered.reduce((a, l) => (atOrBefore(l.pos, a) ? l.pos : a), covered[0]?.pos ?? upTo);
  const record: SummaryRecord = {
    from,
    upTo,
    segment: (u.segment ?? "").trim().slice(0, 600),
    story,
    events: fresh,
    model,
    at: now,
  };

  return {
    ...mem,
    entities,
    address,
    summary: { text: story, upTo, events, model, updatedAt: now },
    archive: [...(mem.archive ?? []), record],
    pending: keepPending,
    updatedAt: now,
  };
}

/** Rough token count for mixed Vietnamese/Japanese/English: CJK about 1 per character, the rest about 1 per 2.6 characters. */
export function estimateTokens(text: string): number {
  let cjk = 0;
  for (let i = 0; i < text.length; i++) {
    const c = text.charCodeAt(i);
    if ((c >= 0x3040 && c <= 0x30ff) || (c >= 0x3400 && c <= 0x9fff) || (c >= 0xff00 && c <= 0xffef)) cjk++;
  }
  return Math.ceil(cjk + (text.length - cjk) / 2.6);
}

/** Token budgets for the memory sent with each page. Well under 100k by design: the whole prompt stays near 5-8k. */
export const MEMORY_BUDGET = { stable: 1200, volatile: 900 };

/**
 * Names active around `pos`: speakers and listeners of the latest dialogue read, and
 * names mentioned in the latest summaries. A series with hundreds of characters only
 * sends the cards that matter for the next page.
 */
export function activeNames(mem: SeriesMemory, pos: ReadingPosition): Set<string> {
  const out = new Set<string>();
  const lines = [...(mem.pending ?? []), ...mem.recent].filter((l) => atOrBefore(l.pos, pos)).slice(-40);
  for (const l of lines) for (const n of [l.speaker, l.to]) if (n && n !== "unknown") out.add(n);
  const records = (mem.archive ?? []).filter((r) => atOrBefore(r.upTo, pos)).slice(-3);
  const text = records.map((r) => r.segment).join(" ");
  for (const e of mem.entities) if (e.kind === "character" && e.vi && text.includes(e.vi)) out.add(e.vi);
  return out;
}

/** Latest summary records written from pages at or before `pos` (never later ones). */
export function recordsUpTo(mem: SeriesMemory, pos: ReadingPosition): SummaryRecord[] {
  return (mem.archive ?? []).filter((r) => atOrBefore(r.upTo, pos));
}

/**
 * Bounded input for a background update: the rolling story, the cast and address
 * rules that the new dialogue involves (plus reader-set ones), never the whole archive.
 * Its size does not grow with the length of the series.
 */
export function backgroundInput(mem: SeriesMemory, maxCast = 20, maxAddress = 24) {
  const involved = new Set<string>();
  for (const l of mem.pending ?? []) for (const n of [l.speaker, l.to]) if (n && n !== "unknown") involved.add(n);
  const chars = mem.entities.filter((e) => e.kind === "character" && e.status !== "rejected");
  const score = (e: MemoryEntity) => (involved.has(e.vi) ? 0 : e.status === "locked" || e.status === "confirmed" ? 1 : 2);
  const cast = [...chars].sort((a, b) => score(a) - score(b) || (b.seen ?? 1) - (a.seen ?? 1)).slice(0, maxCast);
  const names = new Set(cast.map((e) => e.vi));
  return {
    profile: mem.profile,
    story_so_far: mem.summary?.text,
    cast: cast.map((e) => ({ name: e.vi, ja: e.ja, gender: e.gender, role: e.role, speech: e.speech, relations: e.relations })),
    address: mem.address
      .filter((a) => a.status !== "rejected" && (names.has(a.from) || names.has(a.to)))
      .slice(0, maxAddress)
      .map((a) => ({ from: a.from, to: a.to, call: a.call, self_vi: a.selfVi, address_vi: a.addressVi })),
  };
}

const RANK: Record<EntryStatus, number> = { locked: 0, confirmed: 1, auto: 2, rejected: 3 };

/**
 * Stable part of the prompt (series profile, cast cards, directed address matrix,
 * glossary). Changes rarely, so it sits in the cached prefix. Only what is known at
 * or before `pos` is included; metadata characters appear once they have been seen.
 */
export function stableContext(mem: SeriesMemory, pos: ReadingPosition, maxTokens = MEMORY_BUDGET.stable): string {
  const head: string[] = [];
  const p = mem.profile;
  if (p) {
    head.push(
      "Series profile:\n" +
        [
          p.genres.length ? `- genres: ${p.genres.join(", ")}` : "",
          p.tone ? `- tone: ${p.tone}` : "",
          p.setting ? `- setting: ${p.setting}` : "",
          p.register ? `- Vietnamese register: ${p.register}` : "",
          p.synopsis ? `- premise: ${p.synopsis}` : "",
        ]
          .filter(Boolean)
          .join("\n"),
    );
  }
  if (mem.readerNotes?.trim()) head.push(`Reader notes (trusted):\n${mem.readerNotes.trim().slice(0, 1200)}`);

  const active = activeNames(mem, pos);
  const known = mem.entities.filter((e) => e.status !== "rejected" && atOrBefore(e.knownFrom, pos));
  const castLine = (e: MemoryEntity) => {
    const bits = [
      e.gender && e.gender !== "unknown" ? e.gender : "",
      e.role ?? "",
      e.speech ? `speech: ${e.speech}` : "",
      e.relations?.length ? `relations: ${e.relations.join("; ")}` : "",
      e.officialName ? `official spelling: ${e.officialName}` : "",
    ].filter(Boolean);
    return `- ${e.vi} [${e.ja}]${bits.length ? ` (${bits.join(", ")})` : ""} {${e.status}}`;
  };
  const cast = known.filter((e) => e.kind === "character");
  const names = new Set(cast.map((e) => e.vi));
  const addrLine = (a: MemoryAddress) =>
    `- ${a.from} → ${a.to}: ${a.call ? `calls "${a.call}"; ` : ""}self "${a.selfVi ?? "?"}", addresses as "${a.addressVi ?? "?"}"` +
    ` {${a.status}${a.count && a.count > 1 ? `, seen ${a.count}×` : ""}${names.has(a.from) && names.has(a.to) ? "" : ", partial"}}`;
  const matrix = mem.address.filter((a) => a.status !== "rejected" && atOrBefore(a.knownFrom, pos));
  const recentJa = [...(mem.pending ?? []), ...mem.recent].filter((l) => atOrBefore(l.pos, pos)).map((l) => l.ja).join(" ");
  const terms = known.filter((e) => e.kind !== "character");

  // Candidates in priority order; each line is taken while the budget lasts. A long
  // series keeps the same prompt size: reader-set and active entries first.
  type Cand = { section: "cast" | "address" | "terms"; line: string; tier: number; order: number };
  const cands: Cand[] = [];
  const locked = (s: EntryStatus) => s === "locked" || s === "confirmed";
  cast.forEach((e) => cands.push({ section: "cast", line: castLine(e), tier: locked(e.status) ? 0 : active.has(e.vi) ? 1 : 4, order: -(e.seen ?? 1) }));
  matrix.forEach((a) =>
    cands.push({ section: "address", line: addrLine(a), tier: locked(a.status) ? 0 : active.has(a.from) || active.has(a.to) ? 2 : 5, order: -(a.count ?? 1) }),
  );
  terms.forEach((e) =>
    cands.push({ section: "terms", line: `- ${e.ja} → ${e.vi} (${e.kind}, ${e.status})`, tier: locked(e.status) ? 0 : recentJa.includes(e.ja) ? 3 : 6, order: -(e.seen ?? 1) }),
  );
  cands.sort((x, y) => x.tier - y.tier || x.order - y.order);
  let used = estimateTokens(head.join("\n\n"));
  const taken: Record<Cand["section"], string[]> = { cast: [], address: [], terms: [] };
  let dropped = 0;
  for (const c of cands) {
    const t = estimateTokens(c.line) + 1;
    if (used + t > maxTokens) {
      dropped++;
      continue;
    }
    used += t;
    taken[c.section].push(c.line);
  }
  const parts = [...head];
  if (taken.cast.length) parts.push("Cast (reuse the Vietnamese names exactly; locked/confirmed = set by the reader):\n" + taken.cast.join("\n"));
  if (taken.address.length)
    parts.push("Directed address (speaker → listener; apply only when both are known for a bubble; never reverse automatically):\n" + taken.address.join("\n"));
  if (taken.terms.length) parts.push("Terms:\n" + taken.terms.join("\n"));
  if (dropped) parts.push(`(${dropped} older entries not shown: not active on recent pages.)`);
  return parts.join("\n\n") || "(empty — no series knowledge yet)";
}

/**
 * Volatile part: the story so far (only if written from pages at or before `pos`),
 * the latest events and recent dialogue. Placed after the cache breakpoint.
 */
export function volatileContext(mem: SeriesMemory, pos: ReadingPosition, maxTokens = MEMORY_BUDGET.volatile): string {
  const parts: string[] = [];
  let used = 0;
  const fits = (text: string) => {
    const t = estimateTokens(text);
    if (used + t > maxTokens) return false;
    used += t;
    return true;
  };
  // The newest story written from pages at or before `pos`: re-reading an early chapter
  // gets the story as it stood then, never one written from later pages.
  const records = recordsUpTo(mem, pos);
  const last = records[records.length - 1];
  const legacy = mem.summary && !mem.archive?.length && atOrBefore(mem.summary.upTo, pos) ? mem.summary : undefined;
  const story = last?.story || legacy?.text;
  const at = last?.upTo ?? legacy?.upTo;
  if (story && at) {
    const block = `Story so far (up to chapter ${at.chapter} page ${at.page}):\n${story}`;
    if (fits(block)) parts.push(block);
  }
  const segs: string[] = [];
  for (const r of records.slice(-3).reverse()) {
    if (!r.segment) continue;
    const line = `- ch${r.from.chapter} p${r.from.page}–ch${r.upTo.chapter} p${r.upTo.page}: ${r.segment}`;
    if (!fits(line)) break;
    segs.unshift(line);
  }
  if (segs.length) parts.push("Latest developments (oldest first):\n" + segs.join("\n"));
  if (!records.length) {
    const events = (mem.summary?.events ?? []).filter((e) => atOrBefore(e.pos, pos)).slice(-5);
    const block = events.length ? "Key events so far:\n" + events.map((e) => `- ${e.text}`).join("\n") : "";
    if (block && !story && fits(block)) parts.push(block);
  }
  const lines: string[] = [];
  for (const r of mem.recent.filter((l) => atOrBefore(l.pos, pos)).reverse()) {
    const line = `- [${r.speaker}${r.to && r.to !== "unknown" ? `→${r.to}` : ""}] ${r.ja} => ${r.vi}`;
    if (!fits(line)) break;
    lines.unshift(line);
  }
  if (lines.length) parts.push("Recent dialogue (oldest first):\n" + lines.join("\n"));
  return parts.join("\n\n") || "(first page read)";
}

/** Both parts together (kept for callers that do not split for caching). */
export function memoryContext(mem: SeriesMemory, pos: ReadingPosition): string {
  return `${stableContext(mem, pos)}\n\n${volatileContext(mem, pos)}`;
}
