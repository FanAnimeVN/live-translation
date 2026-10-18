import type { NameKind, PageNotes, ReadingPosition, RegionTranslation } from "./types";

export type EntryStatus = "auto" | "confirmed" | "locked" | "rejected";

export interface Evidence {
  pageId: string;
  regionId: string;
  pos: ReadingPosition;
}

export interface MemoryEntity {
  ja: string;
  vi: string;
  kind: NameKind;
  status: EntryStatus;
  note?: string;
  knownFrom: ReadingPosition;
  evidence: Evidence[];
  history: Array<{ at: string; vi: string; status: EntryStatus }>;
}

export interface MemoryAddress {
  from: string;
  to: string;
  call?: string;
  selfVi?: string;
  addressVi?: string;
  status: EntryStatus;
  knownFrom: ReadingPosition;
  evidence: Evidence[];
}

export interface RecentLine {
  pageId: string;
  regionId: string;
  speaker: string;
  ja: string;
  vi: string;
  pos: ReadingPosition;
}

export interface SeriesMemory {
  seriesId: string;
  title: string;
  entities: MemoryEntity[];
  address: MemoryAddress[];
  recent: RecentLine[];
  /** Reader-written recap or character list (cold start). */
  readerNotes?: string;
  updatedAt: string;
}

export function emptyMemory(seriesId: string, title: string): SeriesMemory {
  return { seriesId, title, entities: [], address: [], recent: [], updatedAt: new Date().toISOString() };
}

export const atOrBefore = (a: ReadingPosition, b: ReadingPosition) =>
  a.chapter < b.chapter || (a.chapter === b.chapter && a.page <= b.page);

const RECENT_LIMIT = 16;
const normalizeKey = (s: string) => s.normalize("NFKC").replace(/\s+/g, "");

/**
 * Merge a page's notes and dialogue into the series memory. New names become
 * "auto" proposals; existing entries keep their rendering so names stay stable,
 * and reader-confirmed/locked entries are never overwritten.
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
      if (atOrBefore(pos, existing.knownFrom) && !(pos.chapter === existing.knownFrom.chapter && pos.page === existing.knownFrom.page)) {
        existing.knownFrom = pos;
      }
      continue;
    }
    const entity: MemoryEntity = {
      ja: n.ja,
      vi: n.vi,
      kind: n.kind,
      status: "auto",
      note: n.note,
      knownFrom: pos,
      evidence: [ev],
      history: [{ at: now, vi: n.vi, status: "auto" }],
    };
    entities.push(entity);
    proposals.push(entity);
  }

  const address = mem.address.map((a) => ({ ...a, evidence: [...a.evidence] }));
  for (const a of notes.address) {
    const ev: Evidence = { pageId, regionId: a.evidence, pos };
    const existing = address.find((x) => x.from === a.from && x.to === a.to);
    if (existing) {
      if (existing.status === "auto") {
        existing.call ??= a.call;
        existing.selfVi ??= a.self_vi;
        existing.addressVi ??= a.address_vi;
      }
      existing.evidence.push(ev);
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
    });
  }

  const lines = translations
    .filter((t) => t.role !== "none" && t.role !== "decorative" && (t.ja || t.vi))
    .sort((a, b) => a.seq - b.seq)
    .map((t) => ({ pageId, regionId: t.id, speaker: t.speaker, ja: t.ja, vi: t.vi, pos }));
  const recent = [...mem.recent.filter((r) => r.pageId !== pageId), ...lines].slice(-RECENT_LIMIT);

  return { memory: { ...mem, entities, address, recent, updatedAt: now }, proposals };
}

export function setEntityStatus(mem: SeriesMemory, ja: string, status: EntryStatus, vi?: string): SeriesMemory {
  const key = normalizeKey(ja);
  const now = new Date().toISOString();
  return {
    ...mem,
    updatedAt: now,
    entities: mem.entities.map((e) =>
      normalizeKey(e.ja) === key
        ? { ...e, status, vi: vi ?? e.vi, history: [...e.history, { at: now, vi: vi ?? e.vi, status }] }
        : e,
    ),
  };
}

/**
 * Prompt block with only what is known at or before `pos` (no future facts),
 * locked and confirmed entries first, bounded in size.
 */
export function memoryContext(mem: SeriesMemory, pos: ReadingPosition, maxChars = 3500): string {
  const rank: Record<EntryStatus, number> = { locked: 0, confirmed: 1, auto: 2, rejected: 3 };
  const entities = mem.entities
    .filter((e) => e.status !== "rejected" && atOrBefore(e.knownFrom, pos))
    .sort((a, b) => rank[a.status] - rank[b.status]);
  const address = mem.address.filter((a) => a.status !== "rejected" && atOrBefore(a.knownFrom, pos));
  const recent = mem.recent.filter((r) => atOrBefore(r.pos, pos));

  const parts: string[] = [];
  if (mem.readerNotes?.trim()) parts.push(`Reader notes (trusted):\n${mem.readerNotes.trim()}`);
  if (entities.length) {
    parts.push(
      "Names & terms (reuse these exact Vietnamese renderings; locked/confirmed = set by the reader):\n" +
        entities.map((e) => `- ${e.ja} → ${e.vi} (${e.kind}, ${e.status}${e.note ? `; ${e.note}` : ""})`).join("\n"),
    );
  }
  if (address.length) {
    parts.push(
      "Directed address rules (speaker → listener; never reverse them automatically):\n" +
        address
          .map(
            (a) =>
              `- ${a.from} → ${a.to}: calls ${a.call ? `"${a.call}"` : "?"}; self-term "${a.selfVi ?? "?"}", address-term "${a.addressVi ?? "?"}" (${a.status})`,
          )
          .join("\n"),
    );
  }
  if (recent.length) {
    parts.push(
      "Recent dialogue (oldest first):\n" +
        recent.map((r) => `- [${r.speaker}] ${r.ja} => ${r.vi}`).join("\n"),
    );
  }
  let text = parts.join("\n\n");
  if (!text) return "(empty — first page of this story; build knowledge only from what is shown)";
  if (text.length > maxChars) text = text.slice(text.length - maxChars);
  return text;
}
