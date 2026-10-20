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
  /** How the character is drawn (from a page where they are named and visible), to recognise them later. */
  looks?: string;
  /** Gender as drawn, seen on one page: it becomes `gender` only when a second page agrees (one misread face must not pin the pronouns of a whole series). */
  genderSeen?: { gender: "female" | "male"; pageId: string };
  /** Set when the reader answered the gender question (never changed by a model). */
  genderBy?: "reader";
  /**
   * Where the character's face is drawn on a page already read (per-mille box). Geometry only: the
   * reference is cropped again from that page while it is at hand, never stored as an image.
   */
  ref?: { pageId: string; box: [number, number, number, number] };
  /**
   * Labels this character had before their name was known ("(boy, curly hair)"). A reader's binding
   * makes lines under the label read as this name; a model's is a suggestion shown on the card.
   */
  aliases?: Array<{ label: string; by: "model" | "reader"; pageId?: string }>;
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
  /** Pages where the same speaker → listener used other terms: the rule is ambiguous. */
  conflicts?: number;
  /** Earlier values when the reader changed the rule. */
  history?: Array<{ at: string; selfVi?: string; addressVi?: string; status: EntryStatus }>;
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

export const EVENT_KINDS = ["event", "reveal", "relationship", "promise", "flashback"] as const;
export type EventKind = (typeof EVENT_KINDS)[number];

/**
 * L1 event card: kept for good with its evidence, and only brought back into a prompt
 * when a later line refers to it (`recallEvents`). Cards written before v4 have only
 * text, position and evidence.
 */
export interface StoryEvent {
  text: string;
  /** Last page of its evidence: the card is unknown before this position. */
  pos: ReadingPosition;
  evidence: Evidence[];
  /** Characters taking part, names as in the memory. */
  who?: string[];
  /** 1 minor, 2 matters to the arc, 3 turning point. */
  importance?: 1 | 2 | 3;
  kind?: EventKind;
  /** Words a later line may use to refer back to it, Japanese and Vietnamese. */
  keys?: string[];
}

/**
 * L2 digest: one chapter told from that chapter's L1 cards only, or, for long series, an
 * arc of ARC_CHAPTERS chapters told from their chapter digests. Always rebuilt from its
 * sources, never from an older digest, so errors do not compound.
 */
export interface Digest {
  level: "chapter" | "arc";
  /** First and last chapter covered. */
  chapters: [number, number];
  text: string;
  /** Last page its sources come from: never shown before this position. */
  upTo: ReadingPosition;
  /** Cards (chapter) or chapter digests (arc) it was built from. */
  sources: number;
  model: string;
  at: string;
}

/** L3: the story so far, rebuilt from digests of finished chapters (never from the previous one). */
export interface StoryOverview {
  text: string;
  upTo: ReadingPosition;
  /** Last chapter whose digest went in. */
  chapter: number;
  model: string;
  at: string;
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
  /** Rolling story merged from the previous one: only on records written before v4. */
  story?: string;
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
  /** L2: the latest digest per chapter (and per arc of a long series). */
  digests?: Digest[];
  /** L3 history, oldest first: one per finished chapter, so re-reading gets the story as it stood. */
  overviews?: StoryOverview[];
  /** Dialogue read since the last background summary (bounded). */
  pending?: RecentLine[];
  /** Confirmed external metadata; its characters only surface once seen in the story. */
  metadata?: SeriesMetadata;
  /** Cast questions already put to the reader (cast.ts), so none is asked twice. */
  asked?: Array<{ id: string; at: ReadingPosition; answer: string }>;
  updatedAt: string;
}

export function emptyMemory(seriesId: string, title: string): SeriesMemory {
  return { seriesId, title, entities: [], address: [], recent: [], updatedAt: new Date().toISOString() };
}

/**
 * A speaker or listener the memory may keep: not "unknown" and not a page-local label for someone
 * seen but not yet named, such as "(girl, short hair)". Labels help the next pages keep the same
 * pair of pronouns (recent dialogue) but never become characters or address rules.
 */
export const isNamed = (n: string | undefined): n is string => !!n && n !== "unknown" && !/^\(.*\)$/.test(n.trim());
export const isLabel = (n: string | undefined): n is string => !!n && /^\(.+\)$/.test(n.trim());
const labelKey = (s: string) => s.trim().toLowerCase().replace(/\s+/g, " ");

/** A label bound to a character reads as that character's name; names, "unknown" and unbound labels are returned as given. */
export function resolveName<T extends string | undefined>(entities: MemoryEntity[], n: T): T | string {
  if (!isLabel(n)) return n;
  const k = labelKey(n);
  const e = entities.find((x) => x.kind === "character" && x.status !== "rejected" && x.aliases?.some((a) => a.by === "reader" && labelKey(a.label) === k));
  return e ? e.vi : n;
}

/**
 * Bind `label` to the character `ja`. The reader's binding takes the label from any other character
 * and rewrites the lines and rules under it to the name, so the memory and the next prompts speak of
 * one person. The model's binding is only a suggestion (the guess on the reader's card): applied
 * directly it named more lines (26% → 41%, 21/10) but tied some labels to the wrong character, and
 * pronouns got worse. A reader binding is never replaced by a model suggestion.
 */
export function bindLabel(mem: SeriesMemory, label: string, ja: string, by: "model" | "reader", pageId?: string): SeriesMemory {
  const k = labelKey(label);
  if (by === "model" && mem.entities.some((e) => e.aliases?.some((a) => a.by === "reader" && labelKey(a.label) === k))) return mem;
  const entities = mem.entities.map((e) => {
    const rest = (e.aliases ?? []).filter((a) => labelKey(a.label) !== k);
    if (e.kind === "character" && e.ja === ja) return { ...e, aliases: [...rest, { label, by, ...(pageId && { pageId }) }] };
    return e.aliases ? { ...e, aliases: rest } : e;
  });
  const lines = (ls: RecentLine[]) => ls.map((l) => ({ ...l, speaker: resolveName(entities, l.speaker), to: resolveName(entities, l.to) }));
  const address = mem.address.map((a) => ({ ...a, from: resolveName(entities, a.from), to: resolveName(entities, a.to) }));
  return { ...mem, entities, address, recent: lines(mem.recent), ...(mem.pending && { pending: lines(mem.pending) }) };
}

export const atOrBefore = (a: ReadingPosition, b: ReadingPosition) =>
  a.chapter < b.chapter || (a.chapter === b.chapter && a.page <= b.page);

/** Lines kept for L0 (storage only: the prompt takes `recentLines` of them within its budget). */
const RECENT_LIMIT = 80;
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
      if (n.face && !existing.ref) existing.ref = { pageId, box: n.face };
      if (existing.status === "auto") {
        existing.looks ??= n.looks;
        if ((!existing.gender || existing.gender === "unknown") && n.gender) {
          const seen = existing.genderSeen;
          if (seen && seen.pageId !== pageId && seen.gender === n.gender) existing.gender = n.gender;
          else if (!seen || seen.pageId !== pageId) existing.genderSeen = { gender: n.gender, pageId };
        }
      }
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
      ...(n.looks && { looks: n.looks }),
      ...(n.gender && { genderSeen: { gender: n.gender, pageId } }),
      ...(n.face && { ref: { pageId, box: n.face } }),
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

  // A name now given to someone who had a label on earlier pages: their lines and rules read as the name.
  let bound: SeriesMemory = { ...mem, entities };
  for (const n of notes.names) {
    const e = n.kind === "character" && n.was ? bound.entities.find((x) => normalizeKey(x.ja) === normalizeKey(n.ja)) : undefined;
    if (e && n.was) bound = bindLabel(bound, n.was, e.ja, "model", pageId);
  }
  const ents = bound.entities;

  const address = bound.address.map((a) => ({ ...a, evidence: [...a.evidence] }));
  for (const note of notes.address) {
    const a = { ...note, from: resolveName(ents, note.from), to: resolveName(ents, note.to) };
    if (!isNamed(a.from) || !isNamed(a.to)) continue;
    const ev: Evidence = { pageId, regionId: a.evidence, pos };
    const existing = address.find((x) => x.from === a.from && x.to === a.to);
    if (existing) {
      const agrees = (x?: string, y?: string) => !x || !y || x === y;
      const same = agrees(a.self_vi, existing.selfVi) && agrees(a.address_vi, existing.addressVi);
      if (existing.status === "auto") {
        existing.call ??= a.call;
        existing.selfVi ??= a.self_vi;
        existing.addressVi ??= a.address_vi;
      }
      if (same) existing.count = (existing.count ?? 1) + 1;
      else existing.conflicts = (existing.conflicts ?? 0) + 1;
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
    .map((t) => ({ pageId, regionId: t.id, speaker: resolveName(ents, t.speaker), to: resolveName(ents, t.to), ja: t.ja, vi: t.vi, pos }));
  const recent = [...bound.recent.filter((r) => r.pageId !== pageId), ...lines].slice(-RECENT_LIMIT);
  const pending = [...(bound.pending ?? []).filter((r) => r.pageId !== pageId), ...lines].slice(-PENDING_LIMIT);

  const profile =
    mem.profile ??
    (notes.series && notes.series.genres.length
      ? { genres: notes.series.genres, tone: notes.series.tone, setting: notes.series.setting, source: "page" as const }
      : undefined);

  return { memory: { ...mem, entities: ents, address, recent, pending, profile, updatedAt: now }, proposals };
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
  /** @deprecated Ignored since v4: the story so far is rebuilt from chapter digests, never merged. */
  story_so_far?: string;
  /** What the new dialogue added, on its own. */
  segment?: string;
  events?: Array<{ text: string; evidence?: string[]; who?: string[]; importance?: number; kind?: string; keys?: string[] }>;
  characters?: Array<{ name: string; ja?: string; gender?: string; role?: string; speech?: string; relations?: string[] }>;
  address?: Array<{ from: string; to: string; call?: string; self_vi?: string; address_vi?: string; evidence?: string[] }>;
}

const strings = (xs: unknown, max: number, len: number): string[] =>
  [...new Set((Array.isArray(xs) ? xs : []).filter((x): x is string => typeof x === "string").map((x) => x.trim().slice(0, len)).filter(Boolean))].slice(0, max);

/** A clean L1 card: optional fields only when valid, so v3 and v4 cards read alike. */
function card(text: string, pos: ReadingPosition, evidence: Evidence[], raw: { who?: unknown; importance?: unknown; kind?: unknown; keys?: unknown }): StoryEvent {
  const who = strings(raw.who, 6, 40).filter((n) => isNamed(n) && !/^(không rõ|\?)$/i.test(n));
  const importance = Math.round(Number(raw.importance));
  const kind = (EVENT_KINDS as readonly string[]).includes(String(raw.kind)) ? (raw.kind as EventKind) : undefined;
  const keys = strings(raw.keys, 8, 30);
  return {
    text: text.trim().slice(0, 200),
    pos,
    evidence,
    ...(who.length ? { who } : {}),
    ...(importance >= 1 && importance <= 3 ? { importance: importance as 1 | 2 | 3 } : {}),
    ...(kind ? { kind } : {}),
    ...(keys.length ? { keys } : {}),
  };
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
  for (const raw of u.address ?? []) {
    const a = { ...raw, from: resolveName(mem.entities, raw.from), to: resolveName(mem.entities, raw.to) };
    if (!isNamed(a.from) || !isNamed(a.to)) continue;
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
      const last = ev.reduce<ReadingPosition | undefined>((a, x) => (!a || atOrBefore(a, x.pos) ? x.pos : a), undefined);
      return card(String(e.text ?? ""), last ?? upTo, ev, e);
    })
    .filter((e) => e.text && e.evidence.length);
  const events: StoryEvent[] = [...(mem.summary?.events ?? []), ...fresh].slice(-40);

  const kept = new Set(keepPending.map((l) => `${l.pageId}:${l.regionId}`));
  const covered = (mem.pending ?? []).filter((l) => !kept.has(`${l.pageId}:${l.regionId}`));
  const from = covered.reduce((a, l) => (atOrBefore(l.pos, a) ? l.pos : a), covered[0]?.pos ?? upTo);
  const record: SummaryRecord = {
    from,
    upTo,
    segment: (u.segment ?? "").trim().slice(0, 600),
    events: fresh,
    model,
    at: now,
  };

  return {
    ...mem,
    entities,
    address,
    // Kept for older readers of `summary.events`; the story text now lives in `overviews`.
    summary: { text: "", upTo, events, model, updatedAt: now },
    archive: [...(mem.archive ?? []), record],
    pending: keepPending,
    updatedAt: now,
  };
}

// ---------------------------------------------------------------- L2 / L3 (digests)

/** Chapters per arc digest: a long series feeds L3 from arcs, so its input stays small. */
export const ARC_CHAPTERS = 10;
/** Rebuild the open chapter's digest after this many new cards (once its start has left "latest developments"). */
const DIGEST_EVERY_CARDS = 6;
/** Stored lengths, so each part with its heading fits its share of the volatile budget (200 / 150 tokens). */
const OVERVIEW_CHARS = 460;
const DIGEST_CHARS = 330;

/** Every L1 card known, oldest first (archive records; the pre-archive summary for old memories). */
export function allCards(mem: SeriesMemory): StoryEvent[] {
  const archived = (mem.archive ?? []).flatMap((r) => r.events);
  return archived.length ? archived : (mem.summary?.events ?? []);
}

/** Furthest page read so far (dialogue, pending lines and summaries). */
export function frontier(mem: SeriesMemory): ReadingPosition | undefined {
  const all = [...mem.recent.map((l) => l.pos), ...(mem.pending ?? []).map((l) => l.pos), ...(mem.archive ?? []).map((r) => r.upTo)];
  return all.reduce<ReadingPosition | undefined>((a, p) => (!a || atOrBefore(a, p) ? p : a), undefined);
}

const lastPos = (ps: ReadingPosition[]) => ps.reduce((a, p) => (atOrBefore(a, p) ? p : a), ps[0]);

/**
 * Chapter digests to (re)build, oldest first: a finished chapter (the reader has moved
 * past it) whose digest is missing or misses cards, and the open chapter once enough
 * new cards arrived that its start no longer fits in "latest developments".
 */
export function chapterDigestsDue(mem: SeriesMemory): Array<{ chapter: number; finished: boolean; cards: StoryEvent[] }> {
  const front = frontier(mem);
  if (!front) return [];
  const by = new Map<number, StoryEvent[]>();
  for (const c of allCards(mem)) by.set(c.pos.chapter, [...(by.get(c.pos.chapter) ?? []), c]);
  const out: Array<{ chapter: number; finished: boolean; cards: StoryEvent[] }> = [];
  for (const [chapter, cards] of [...by].sort((a, b) => a[0] - b[0])) {
    const d = (mem.digests ?? []).find((x) => x.level === "chapter" && x.chapters[0] === chapter);
    const finished = chapter < front.chapter;
    const records = (mem.archive ?? []).filter((r) => r.upTo.chapter === chapter).length;
    const due = finished ? d?.sources !== cards.length : records > 3 && cards.length - (d?.sources ?? 0) >= DIGEST_EVERY_CARDS;
    if (due) out.push({ chapter, finished, cards });
  }
  return out;
}

/** Arcs of finished chapters whose digest is missing or out of date. */
export function arcDigestsDue(mem: SeriesMemory): Array<{ chapters: [number, number]; digests: Digest[] }> {
  const front = frontier(mem);
  if (!front) return [];
  const chapters = (mem.digests ?? []).filter((d) => d.level === "chapter");
  const blocks = new Set(chapters.map((d) => Math.floor((d.chapters[0] - 1) / ARC_CHAPTERS)));
  const out: Array<{ chapters: [number, number]; digests: Digest[] }> = [];
  for (const b of [...blocks].sort((x, y) => x - y)) {
    const range: [number, number] = [b * ARC_CHAPTERS + 1, (b + 1) * ARC_CHAPTERS];
    if (range[1] >= front.chapter) continue; // the arc is still being read
    const ds = chapters.filter((d) => d.chapters[0] >= range[0] && d.chapters[0] <= range[1]).sort((x, y) => x.chapters[0] - y.chapters[0]);
    const arc = (mem.digests ?? []).find((d) => d.level === "arc" && d.chapters[0] === range[0]);
    const upTo = lastPos(ds.map((d) => d.upTo));
    if (!arc || arc.sources !== ds.length || !atOrBefore(upTo, arc.upTo)) out.push({ chapters: range, digests: ds });
  }
  return out;
}

/** What L3 is built from at `pos`: arcs of finished blocks, then digests of the other finished chapters. */
export function overviewSources(mem: SeriesMemory, pos: ReadingPosition): Digest[] {
  const done = (mem.digests ?? []).filter((d) => d.chapters[1] < pos.chapter && atOrBefore(d.upTo, pos));
  const arcs = done.filter((d) => d.level === "arc");
  const inArc = (c: number) => arcs.some((a) => a.chapters[0] <= c && c <= a.chapters[1]);
  return [...arcs, ...done.filter((d) => d.level === "chapter" && !inArc(d.chapters[0]))].sort((a, b) => a.chapters[0] - b.chapters[0]);
}

/** L3 is rebuilt when a finished chapter (or arc) got a new digest — never merged into the old text. */
export function overviewDue(mem: SeriesMemory): boolean {
  const front = frontier(mem);
  const src = front ? overviewSources(mem, front) : [];
  if (!src.length) return false;
  const latest = mem.overviews?.[mem.overviews.length - 1];
  const upTo = lastPos(src.map((d) => d.upTo));
  return !latest || latest.chapter < Math.max(...src.map((d) => d.chapters[1])) || !atOrBefore(upTo, latest.upTo);
}

/** Bounded model input for a digest: the chapter's cards (or the arc's chapter digests), never an older digest. */
export function digestInput(sources: StoryEvent[] | Digest[], maxCards = 60): string {
  if (!sources.length) return "";
  if ("level" in sources[0]) return (sources as Digest[]).map((d) => `- chapter ${d.chapters[0]}${d.chapters[1] !== d.chapters[0] ? `–${d.chapters[1]}` : ""}: ${d.text}`).join("\n");
  let cards = sources as StoryEvent[];
  if (cards.length > maxCards) {
    // Keep turning points first, then the latest; order stays chronological.
    const keep = new Set([...cards].map((c, i) => ({ c, i })).sort((a, b) => (b.c.importance ?? 1) - (a.c.importance ?? 1) || b.i - a.i).slice(0, maxCards).map((x) => x.i));
    cards = cards.filter((_, i) => keep.has(i));
  }
  return cards
    .map((c) => `- p${c.pos.page}${c.kind ? ` [${c.kind}${c.importance ? `, ${c.importance}` : ""}]` : ""}${c.who?.length ? ` (${c.who.join(", ")})` : ""}: ${c.text}`)
    .join("\n");
}

export function makeDigest(level: Digest["level"], chapters: [number, number], text: string, sources: StoryEvent[] | Digest[], model: string): Digest {
  const ups = (sources as Array<StoryEvent | Digest>).map((s) => ("level" in s ? s.upTo : s.pos));
  return { level, chapters, text: text.trim().slice(0, DIGEST_CHARS), upTo: lastPos(ups), sources: sources.length, model, at: new Date().toISOString() };
}

export function makeOverview(text: string, sources: Digest[], model: string): StoryOverview {
  return {
    text: text.trim().slice(0, OVERVIEW_CHARS),
    upTo: lastPos(sources.map((d) => d.upTo)),
    chapter: Math.max(...sources.map((d) => d.chapters[1])),
    model,
    at: new Date().toISOString(),
  };
}

/** Store new digests (replacing the one for the same chapter/arc) and an overview (one per chapter). */
export function applyDigests(mem: SeriesMemory, digests: Digest[], overview?: StoryOverview): SeriesMemory {
  if (!digests.length && !overview) return mem;
  const same = (a: Digest, b: Digest) => a.level === b.level && a.chapters[0] === b.chapters[0];
  const kept = (mem.digests ?? []).filter((d) => !digests.some((n) => same(d, n)));
  const overviews = overview ? [...(mem.overviews ?? []).filter((o) => o.chapter !== overview.chapter), overview] : mem.overviews;
  return {
    ...mem,
    digests: [...kept, ...digests].sort((a, b) => a.chapters[0] - b.chapters[0] || (a.level === "arc" ? 1 : -1)),
    overviews,
    updatedAt: new Date().toISOString(),
  };
}

// ---------------------------------------------------------------- L1 recall

export interface RecallQuery {
  who?: string[];
  keys?: string[];
  /** Text of the referring lines: a card key found in it counts as a keyword hit. */
  text?: string;
  /** Also return cards that start on the page being read (default: earlier pages only). */
  includeCurrentPage?: boolean;
  /** In the same chapter, only cards at least this many pages back (earlier chapters always qualify). */
  minPagesBack?: number;
  /** Only cards from at least this many chapters before the reading position. */
  minChaptersBack?: number;
}

/**
 * The recall pass (revising a line with an earlier event) takes cards from earlier chapters
 * only: the open chapter is already in every prompt (its digest and the recent dialogue).
 */
export const RECALL_MIN_CHAPTERS = 1;

/**
 * A P/S is for what readers may really have forgotten: an important event dozens of chapters
 * back. Scanlation teams add such notes rarely; one about a page read minutes ago annoys more
 * than it helps (unfiltered run of 19/10/2026: 82% of notes cited 1–3 pages back).
 */
export const PS_MIN_CHAPTERS = 20;
export const PS_MIN_IMPORTANCE = 2;

/** Whether a recalled event deserves a P/S for a reader at `pos`. */
export function psWorthy(r: RecalledEvent, pos: ReadingPosition): boolean {
  return pos.chapter - r.at.chapter >= PS_MIN_CHAPTERS && (r.event.importance ?? 1) >= PS_MIN_IMPORTANCE;
}

export interface RecalledEvent {
  event: StoryEvent;
  score: number;
  /** Where it happened: the earliest page of its evidence. */
  at: ReadingPosition;
  pageId: string;
}

const fold = (s: string) => s.normalize("NFKC").toLowerCase().replace(/\s+/g, " ").trim();
const samePage = (a: ReadingPosition, b: ReadingPosition) => a.chapter === b.chapter && a.page === b.page;

/**
 * Every name the cast table knows for whoever `name` refers to: the Japanese, the Vietnamese
 * rendering, the official romanization and earlier renderings the reader changed. A line may
 * say ノラトラ where a card says "Nora-tora". Two separate entries are never merged here:
 * whether two names are one character is the reader's call, not the matcher's.
 */
export function nameForms(mem: SeriesMemory, name: string): string[] {
  const forms = new Set([name]);
  const f = fold(name);
  if (!f) return [];
  for (const e of mem.entities) {
    if (e.status === "rejected") continue;
    const all = [e.ja, e.vi, e.officialName, ...e.history.map((h) => h.vi)].filter((x): x is string => !!x?.trim());
    if (all.some((x) => fold(x) === f || normalizeKey(x) === normalizeKey(name))) for (const x of all) forms.add(x);
  }
  return [...forms];
}

/** Query names or keywords as groups of folded forms: one group per thing named, aliases merged. */
function nameGroups(mem: SeriesMemory, names: string[], minChars: number): string[][] {
  const out: string[][] = [];
  const seen = new Set<string>();
  for (const n of names) {
    const forms = [...new Set(nameForms(mem, n).map(fold))].filter((x) => x && x !== "unknown" && [...x].length >= minChars);
    const id = [...forms].sort().join("|");
    if (!forms.length || seen.has(id)) continue;
    seen.add(id);
    out.push(forms);
  }
  return out;
}

/**
 * L1 cards a page refers back to. Pure, and spoiler-safe by construction: a card whose
 * position or any evidence lies after `pos` is never returned. Ranked by participant and
 * keyword overlap, then importance, then recency. With keywords in the query, a card must
 * match at least one: a shared character alone is not a reference to that event. Names
 * match through the cast table (`nameForms`), each person or keyword counting once.
 */
export function recallEvents(mem: SeriesMemory, pos: ReadingPosition, q: RecallQuery, max = 4): RecalledEvent[] {
  const who = nameGroups(mem, q.who ?? [], 1);
  const keys = nameGroups(mem, q.keys ?? [], 2);
  const text = fold(q.text ?? "");
  const cards = allCards(mem);
  const out: RecalledEvent[] = [];
  const seen = new Set<string>();
  cards.forEach((e, i) => {
    if (!atOrBefore(e.pos, pos) || e.evidence.some((x) => !atOrBefore(x.pos, pos))) return;
    const first = e.evidence.reduce<Evidence | undefined>((a, x) => (!a || atOrBefore(x.pos, a.pos) ? x : a), undefined);
    const at = first?.pos ?? e.pos;
    if (!q.includeCurrentPage && samePage(at, pos)) return;
    if (q.minPagesBack && at.chapter === pos.chapter && pos.page - at.page < q.minPagesBack) return;
    if (q.minChaptersBack && pos.chapter - at.chapter < q.minChaptersBack) return;
    const cardKeys = (e.keys ?? []).map(fold).filter((k) => [...k].length >= 2);
    const hay = fold([e.text, ...cardKeys].join(" | "));
    const cardWho = new Set((e.who ?? []).map(fold));
    const whoHits = who.filter((g) => g.some((w) => cardWho.has(w) || hay.includes(w))).length;
    const hits = new Set(keys.filter((g) => g.some((k) => hay.includes(k) || cardKeys.some((c) => k.includes(c)))).map((g) => g[0]));
    if (text) for (const c of cardKeys) if (text.includes(c) && !keys.some((g) => g.includes(c) && hits.has(g[0]))) hits.add(c);
    if (keys.length || text ? !hits.size : !whoHits) return;
    const key = fold(e.text);
    if (seen.has(key)) return;
    seen.add(key);
    const recency = cards.length > 1 ? i / (cards.length - 1) : 1;
    out.push({ event: e, score: 3 * whoHits + 2 * hits.size + (e.importance ?? 1) + recency, at, pageId: first?.pageId ?? "" });
  });
  return out.sort((a, b) => b.score - a.score).slice(0, max);
}

/** Recalled cards as prompt lines (ids c1…), within the recall budget. */
export function recallContext(cards: RecalledEvent[], maxTokens = MEMORY_BUDGET.recall): string {
  const lines: string[] = [];
  let used = 0;
  cards.forEach((c, i) => {
    const e = c.event;
    const meta = [`chapter ${c.at.chapter}, page ${c.at.page}`, e.kind, e.who?.length ? e.who.join(", ") : ""].filter(Boolean).join("; ");
    const line = `c${i + 1} (${meta}): ${e.text}${e.keys?.length ? ` [keys: ${e.keys.join(", ")}]` : ""}`;
    const t = estimateTokens(line) + 1;
    if (used + t > maxTokens) return;
    used += t;
    lines.push(line);
  });
  return lines.join("\n");
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

/**
 * Token budgets for the memory sent with each page, the same for chapter 1 and chapter 500.
 * `recall` is only spent on the few pages whose lines refer back to earlier events.
 */
export const MEMORY_BUDGET = { stable: 1200, volatile: 900, recall: 400 };
/** Shares inside the volatile budget: L3 story, L2 chapter digest, L0 recent dialogue. */
const VOLATILE_PARTS = { story: 200, chapter: 150, recent: 600 };
/**
 * Default L0 size K (recent lines sent with every page). Run of 19/10/2026 (60 pages, K in
 * 0–80): no K separable from K=80 on chrF; K=10 is within 98% of it with near-best judged
 * pronoun/speaker errors, at ~400 tokens. See docs/STORY-MEMORY.md §9.
 */
export const RECENT_LINES = 10;

export interface VolatileOptions {
  /** L0 size K: at most this many recent lines. */
  recentLines?: number;
  /** Token cap for L0 inside the volatile budget. */
  recentTokens?: number;
}

/**
 * Names active around `pos`: speakers and listeners of the latest dialogue read, and
 * names mentioned in the latest summaries. A series with hundreds of characters only
 * sends the cards that matter for the next page.
 */
export function activeNames(mem: SeriesMemory, pos: ReadingPosition): Set<string> {
  const out = new Set<string>();
  const lines = [...(mem.pending ?? []), ...mem.recent].filter((l) => atOrBefore(l.pos, pos)).slice(-40);
  for (const l of lines) for (const n of [l.speaker, l.to]) if (isNamed(n)) out.add(n);
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
  for (const l of mem.pending ?? []) for (const n of [l.speaker, l.to]) if (isNamed(n)) involved.add(n);
  const chars = mem.entities.filter((e) => e.kind === "character" && e.status !== "rejected");
  const score = (e: MemoryEntity) => (involved.has(e.vi) ? 0 : e.status === "locked" || e.status === "confirmed" ? 1 : 2);
  const cast = [...chars].sort((a, b) => score(a) - score(b) || (b.seen ?? 1) - (a.seen ?? 1)).slice(0, maxCast);
  const names = new Set(cast.map((e) => e.vi));
  const front = frontier(mem);
  return {
    profile: mem.profile,
    // Context only (the update never rewrites it): L3 plus the open chapter's digest.
    story_so_far: front ? storyAt(mem, front).join("\n") || undefined : undefined,
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
      e.looks ? `looks: ${e.looks}` : "",
      e.aliases?.some((a) => a.by === "reader") ? `aka ${e.aliases.filter((a) => a.by === "reader").map((a) => a.label).join(", ")}` : "",
      e.speech ? `speech: ${e.speech}` : "",
      e.relations?.length ? `relations: ${e.relations.join("; ")}` : "",
      e.officialName ? `official spelling: ${e.officialName}` : "",
    ].filter(Boolean);
    return `- ${e.vi} [${e.ja}]${bits.length ? ` (${bits.join(", ")})` : ""} {${e.status}}`;
  };
  const cast = known.filter((e) => e.kind === "character");
  const names = new Set(cast.map((e) => e.vi));
  // Confidence the model can act on: a rule seen on one page or contradicted on another is only a hint.
  const confidence = (a: MemoryAddress) =>
    a.status !== "auto" ? "" : a.conflicts ? `, ambiguous: contradicted ${a.conflicts}×` : (a.count ?? 1) < 2 ? ", tentative" : "";
  const addrLine = (a: MemoryAddress) =>
    `- ${a.from} → ${a.to}: ${a.call ? `calls "${a.call}"; ` : ""}self "${a.selfVi ?? "?"}", addresses as "${a.addressVi ?? "?"}"` +
    ` {${a.status}${a.count && a.count > 1 ? `, seen ${a.count}×` : ""}${confidence(a)}${names.has(a.from) && names.has(a.to) ? "" : ", partial"}}`;
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
    parts.push(
      "Directed address (speaker → listener; apply only when both are known for a bubble; never reverse automatically; locked/confirmed = the reader's choice, always follow it; tentative or ambiguous = a hint, what the page shows wins):\n" +
        taken.address.join("\n"),
    );
  if (taken.terms.length) parts.push("Terms:\n" + taken.terms.join("\n"));
  if (dropped) parts.push(`(${dropped} older entries not shown: not active on recent pages.)`);
  return parts.join("\n\n") || "(empty — no series knowledge yet)";
}

interface Shown {
  block: string;
  upTo: ReadingPosition;
}

/**
 * Summaries usable at `pos`, each written only from pages at or before it: the newest L3
 * overview (or, for memories written before v4, their last rolling story), and the open
 * chapter's L2 digest or, early in a chapter, the previous chapter's.
 */
function summariesAt(mem: SeriesMemory, pos: ReadingPosition): { story?: Shown; chapter?: Shown } {
  const ov = (mem.overviews ?? []).filter((o) => atOrBefore(o.upTo, pos)).sort((a, b) => a.chapter - b.chapter).pop();
  let story: Shown | undefined;
  if (ov) story = { upTo: ov.upTo, block: `Story so far (chapters 1–${ov.chapter}, from chapter summaries):\n${ov.text}` };
  else {
    const rec = [...recordsUpTo(mem, pos)].reverse().find((r) => r.story);
    const old =
      rec ? { text: rec.story!, upTo: rec.upTo }
      : mem.summary?.text && !mem.archive?.length && atOrBefore(mem.summary.upTo, pos) ? { text: mem.summary.text, upTo: mem.summary.upTo }
      : undefined;
    if (old) story = { upTo: old.upTo, block: `Story so far (up to chapter ${old.upTo.chapter} page ${old.upTo.page}):\n${old.text.slice(0, OVERVIEW_CHARS)}` };
  }
  const ds = (mem.digests ?? []).filter((d) => d.level === "chapter" && atOrBefore(d.upTo, pos));
  const cur = ds.find((d) => d.chapters[0] === pos.chapter);
  const prev = cur ? undefined : ds.filter((d) => d.chapters[0] < pos.chapter).sort((a, b) => b.chapters[0] - a.chapters[0])[0];
  const chapter =
    cur ? { upTo: cur.upTo, block: `This chapter so far (chapter ${pos.chapter}, up to page ${cur.upTo.page}):\n${cur.text}` }
    : prev ? { upTo: prev.upTo, block: `Previous chapter (chapter ${prev.chapters[0]}):\n${prev.text}` }
    : undefined;
  return { story, chapter };
}

/** L3 and L2 blocks usable at `pos` (context for the background model). */
export function storyAt(mem: SeriesMemory, pos: ReadingPosition): string[] {
  const s = summariesAt(mem, pos);
  return [s.story?.block, s.chapter?.block].filter((b): b is string => !!b);
}

/**
 * Volatile part, after the cache breakpoint: L3 story so far, L2 chapter digest, the newest
 * segments no summary covers yet, and L0 (the K most recent lines). Everything is written
 * only from pages at or before `pos`, and the whole stays within `maxTokens` however long
 * the series is. L1 cards are not here: they come back only through `recallEvents`.
 */
export function volatileContext(mem: SeriesMemory, pos: ReadingPosition, maxTokens = MEMORY_BUDGET.volatile, opts: VolatileOptions = {}): string {
  let used = 0;
  const fits = (text: string, cap = Infinity) => {
    const t = estimateTokens(text);
    if (t > cap || used + t > maxTokens) return false;
    used += t;
    return true;
  };
  const s = summariesAt(mem, pos);
  const story = s.story && fits(s.story.block, VOLATILE_PARTS.story) ? s.story : undefined;
  const chapter = s.chapter && fits(s.chapter.block, VOLATILE_PARTS.chapter) ? s.chapter : undefined;

  // Headings and blank lines count too.
  const RECENT_HEAD = "Recent dialogue (oldest first):\n";
  const DEV_HEAD = "Latest developments (oldest first):\n";
  used += 2 * (story ? 1 : 0) + 2 * (chapter ? 1 : 0);
  const k = opts.recentLines ?? RECENT_LINES;
  const recentCap = Math.min(opts.recentTokens ?? VOLATILE_PARTS.recent, maxTokens - used - estimateTokens(RECENT_HEAD) - 2);
  const lines: string[] = [];
  let recentUsed = 0;
  for (const r of mem.recent.filter((l) => atOrBefore(l.pos, pos)).reverse()) {
    if (lines.length >= k) break;
    const line = `- [${r.speaker}${r.to && r.to !== "unknown" ? `→${r.to}` : ""}] ${r.ja} => ${r.vi}`;
    const t = estimateTokens(line);
    if (recentUsed + t + 1 > recentCap) break;
    recentUsed += t + 1;
    lines.unshift(line);
  }
  if (lines.length) used += recentUsed + estimateTokens(RECENT_HEAD) + 2;

  // What happened since the newest summary shown, in what the budget has left.
  const since = [story?.upTo, chapter?.upTo].filter((p): p is ReadingPosition => !!p).reduce<ReadingPosition | undefined>((a, p) => (!a || atOrBefore(a, p) ? p : a), undefined);
  const records = recordsUpTo(mem, pos);
  const segs: string[] = [];
  for (const r of records.slice(-3).reverse()) {
    if (!r.segment || (since && atOrBefore(r.upTo, since))) continue;
    const line = `- ch${r.from.chapter} p${r.from.page}–ch${r.upTo.chapter} p${r.upTo.page}: ${r.segment}`;
    if (!fits(segs.length ? line + "\n" : DEV_HEAD + line + "\n\n")) break;
    segs.unshift(line);
  }
  let events = "";
  if (!records.length && !story) {
    const old = (mem.summary?.events ?? []).filter((e) => atOrBefore(e.pos, pos)).slice(-5);
    const block = old.length ? "Key events so far:\n" + old.map((e) => `- ${e.text}`).join("\n") : "";
    if (block && fits(block)) events = block;
  }

  const parts = [story?.block, chapter?.block, segs.length ? DEV_HEAD + segs.join("\n") : "", events, lines.length ? RECENT_HEAD + lines.join("\n") : ""];
  return parts.filter(Boolean).join("\n\n") || "(first page read)";
}

/** Both parts together (kept for callers that do not split for caching). */
export function memoryContext(mem: SeriesMemory, pos: ReadingPosition): string {
  return `${stableContext(mem, pos)}\n\n${volatileContext(mem, pos)}`;
}
