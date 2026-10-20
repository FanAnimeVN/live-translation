/**
 * One-tap cast questions. The few facts that decide the pronouns of a whole series (is this
 * character male or female? which pair do these two use?) are put to the reader when the model is
 * unsure, and the answer is locked: reader locks always beat model proposals. Each answer is also a
 * labelled example (who → whom, the model's guess, the reader's choice) for measuring and improving
 * the defaults; it holds text only, never an image.
 *
 * Confidence of a model-made fact, lowest first: seen on one page ("tentative") or contradicted
 * ("ambiguous") → agreed on two pages ("likely", used without asking) → set by the reader (locked).
 * A model alone never reaches "locked".
 */
import { atOrBefore, bindLabel, isLabel, isNamed, resolveName, type Evidence, type MemoryAddress, type RecentLine, type SeriesMemory } from "./memory";
import type { ReadingPosition } from "./types";

/** A preset names both directions explicitly, so choosing one is the reader's decision, not a derived reverse. */
export const PAIR_PRESETS = {
  "anh-em": { ab: ["anh", "em"], ba: ["em", "anh"], flip: "em-anh" },
  "em-anh": { ab: ["em", "anh"], ba: ["anh", "em"], flip: "anh-em" },
  "chi-em": { ab: ["chị", "em"], ba: ["em", "chị"], flip: "em-chi" },
  "em-chi": { ab: ["em", "chị"], ba: ["chị", "em"], flip: "chi-em" },
  "to-cau": { ab: ["tớ", "cậu"], ba: ["tớ", "cậu"], flip: "to-cau" },
  "tao-may": { ab: ["tao", "mày"], ba: ["tao", "mày"], flip: "tao-may" },
  "con-bo": { ab: ["con", "bố"], ba: ["bố", "con"], flip: "bo-con" },
  "bo-con": { ab: ["bố", "con"], ba: ["con", "bố"], flip: "con-bo" },
  "con-me": { ab: ["con", "mẹ"], ba: ["mẹ", "con"], flip: "me-con" },
  "me-con": { ab: ["mẹ", "con"], ba: ["con", "mẹ"], flip: "con-me" },
} as const;
export type PairPreset = keyof typeof PAIR_PRESETS;
export const isPairPreset = (s: string): s is PairPreset => s in PAIR_PRESETS;

/** Button text: "Kenta là anh, Yui là em", or "Ngang hàng: tớ–cậu" when both use the same terms. */
export function presetShort(p: PairPreset, a: string, b: string): string {
  const { ab, ba } = PAIR_PRESETS[p];
  return ab[0] === ba[0] ? `Ngang hàng: ${ab[0]}–${ab[1]}` : `${a} là ${ab[0]}, ${b} là ${ba[0]}`;
}

/** "Kenta xưng anh, gọi Yui là em · Yui xưng em, gọi Kenta là anh" */
export function presetLabel(p: PairPreset, a: string, b: string): string {
  const { ab, ba } = PAIR_PRESETS[p];
  return `${a} xưng ${ab[0]}, gọi ${b} là ${ab[1]} · ${b} xưng ${ba[0]}, gọi ${a} là ${ba[1]}`;
}

export interface CastQuestion {
  /** "who:<label>", "gender:<ja>" or "pair:<ja A>|<ja B>". */
  id: string;
  /** who: which character is this label ("(boy, curly hair)")? It unlocks names, rules and the other questions. */
  kind: "who" | "gender" | "pair";
  /** Vietnamese name as the memory and speaker fields write it, and the Japanese key (a label for both when not named). */
  who: Array<{ vi: string; ja: string }>;
  /** What the model believes now: "female" / "male", a preset id, or "self/address". */
  guess?: string;
  /** Lines read so far that involve them: how much the answer matters. */
  lines: number;
  /** A few of those lines, to show with the question. */
  evidence: Evidence[];
}

/**
 * Answers: "name:<ja>" or "new:<name>" (who), "female" | "male" (gender), a PairPreset (pair),
 * "unknown" (never ask again) or "later" (snooze).
 */
export type CastAnswer = "female" | "male" | "unknown" | "later" | PairPreset | `name:${string}` | `new:${string}`;

export const CAST_MIN_LINES = { who: 4, gender: 3, pair: 2 };
const SNOOZE_PAGES = 10;
const locked = (a?: MemoryAddress) => !!a && (a.status === "locked" || a.status === "confirmed");
const likely = (a?: MemoryAddress) => !!a && a.status === "auto" && (a.count ?? 1) >= 2 && !a.conflicts;

function readLines(mem: SeriesMemory, pos: ReadingPosition): RecentLine[] {
  const seen = new Set<string>();
  const out: RecentLine[] = [];
  for (const l of [...mem.recent, ...(mem.pending ?? [])]) {
    const key = `${l.pageId}:${l.regionId}`;
    if (seen.has(key) || !atOrBefore(l.pos, pos)) continue;
    seen.add(key);
    out.push(l);
  }
  return out;
}

function guessPreset(ab?: MemoryAddress, ba?: MemoryAddress): string | undefined {
  if (!ab?.selfVi && !ab?.addressVi && !ba?.selfVi && !ba?.addressVi) return undefined;
  const fits = (r: MemoryAddress | undefined, terms: readonly string[]) =>
    !r || ((!r.selfVi || r.selfVi.toLowerCase() === terms[0]) && (!r.addressVi || r.addressVi.toLowerCase() === terms[1]));
  const p = (Object.keys(PAIR_PRESETS) as PairPreset[]).find((k) => fits(ab, PAIR_PRESETS[k].ab) && fits(ba, PAIR_PRESETS[k].ba));
  return p ?? `${ab?.selfVi ?? "?"}/${ab?.addressVi ?? "?"}`;
}

/**
 * The questions worth one tap at `pos`, most useful first: characters who talk a lot but whose
 * gender is unknown, and pairs who talk to each other but whose address is unknown, tentative or
 * ambiguous. Facts the reader set, or two pages agreed on, are not asked.
 */
export function castQuestions(mem: SeriesMemory, pos: ReadingPosition, max = 2, minLines: Partial<typeof CAST_MIN_LINES> = {}): CastQuestion[] {
  const min = { ...CAST_MIN_LINES, ...minLines };
  const skip = new Set(
    (mem.asked ?? []).filter((a) => a.answer !== "later" || (a.at.chapter === pos.chapter && pos.page - a.at.page < SNOOZE_PAGES)).map((a) => a.id),
  );
  const cast = mem.entities.filter((e) => e.kind === "character" && e.status !== "rejected" && atOrBefore(e.knownFrom, pos));
  const byVi = new Map(cast.map((e) => [e.vi, e]));
  const lines = readLines(mem, pos)
    .map((l) => ({ ...l, speaker: resolveName(mem.entities, l.speaker), to: resolveName(mem.entities, l.to) }))
    .filter((l) => isNamed(l.speaker) || isNamed(l.to) || isLabel(l.speaker) || isLabel(l.to));
  const out: Array<CastQuestion & { score: number }> = [];
  const ev = (ls: RecentLine[]) => ls.slice(0, 2).map((l) => ({ pageId: l.pageId, regionId: l.regionId, pos: l.pos }));

  // Labels the model keeps for someone across pages but cannot name: one tap names them for the whole series.
  const labels = new Map<string, RecentLine[]>();
  for (const l of lines) for (const n of new Set([l.speaker, l.to])) if (isLabel(n)) labels.set(n, [...(labels.get(n) ?? []), l]);
  for (const [label, ls] of labels) {
    if (ls.length < min.who || skip.has(`who:${label}`)) continue;
    const k = label.trim().toLowerCase();
    const guess = mem.entities.find((e) => e.kind === "character" && e.aliases?.some((a) => a.by === "model" && a.label.trim().toLowerCase() === k))?.vi;
    out.push({ id: `who:${label}`, kind: "who", who: [{ vi: label, ja: label }], guess, lines: ls.length, evidence: ev([...ls.filter((l) => l.speaker === label), ...ls]), score: 3 * ls.length });
  }

  for (const e of cast) {
    if (e.gender === "female" || e.gender === "male" || skip.has(`gender:${e.ja}`)) continue;
    const mine = lines.filter((l) => l.speaker === e.vi || l.to === e.vi);
    if (mine.length < min.gender) continue;
    out.push({
      id: `gender:${e.ja}`,
      kind: "gender",
      who: [{ vi: e.vi, ja: e.ja }],
      guess: e.genderSeen?.gender,
      lines: mine.length,
      evidence: [...new Set([...mine.filter((l) => l.speaker === e.vi), ...mine])].slice(0, 2).map((l) => ({ pageId: l.pageId, regionId: l.regionId, pos: l.pos })),
      score: mine.length,
    });
  }

  // Pairs of named characters, or of labels the model keeps stable (a reader-set rule on a label is still the reader's).
  const person = (n?: string) => (n && byVi.has(n) ? { vi: n, ja: byVi.get(n)!.ja } : isLabel(n) ? { vi: n, ja: n } : undefined);
  const pairs = new Map<string, { a: string; b: string; lines: RecentLine[] }>();
  for (const l of lines) {
    if (!person(l.speaker) || !person(l.to) || l.speaker === l.to) continue;
    const key = [l.speaker, l.to!].sort().join("\u0000");
    const p = pairs.get(key) ?? { a: l.speaker, b: l.to!, lines: [] };
    p.lines.push(l);
    pairs.set(key, p);
  }
  for (const { a, b, lines: ls } of pairs.values()) {
    const ea = person(a)!, eb = person(b)!;
    const id = `pair:${ea.ja}|${eb.ja}`;
    if (ls.length < min.pair || skip.has(id) || skip.has(`pair:${eb.ja}|${ea.ja}`)) continue;
    const ab = mem.address.find((r) => r.from === a && r.to === b && r.status !== "rejected");
    const ba = mem.address.find((r) => r.from === b && r.to === a && r.status !== "rejected");
    if ((locked(ab) || likely(ab)) && (locked(ba) || likely(ba))) continue;
    out.push({
      id,
      kind: "pair",
      who: [
        { vi: a, ja: ea.ja },
        { vi: b, ja: eb.ja },
      ],
      guess: guessPreset(ab, ba),
      lines: ls.length,
      evidence: ev(ls),
      score: 2 * ls.length,
    });
  }
  return out
    .sort((x, y) => y.score - x.score)
    .slice(0, max)
    .map(({ score: _, ...q }) => q);
}

/** Apply the reader's answer. Gender and pair answers are locked; the question is not asked again. */
export function answerCast(mem: SeriesMemory, q: CastQuestion, answer: CastAnswer, pos: ReadingPosition, now = new Date().toISOString()): SeriesMemory {
  const asked = [...(mem.asked ?? []).filter((a) => a.id !== q.id), { id: q.id, at: pos, answer }];
  if (q.kind === "who" && (answer.startsWith("name:") || answer.startsWith("new:"))) {
    const label = q.who[0].vi;
    let next = mem;
    let ja = answer.slice(answer.indexOf(":") + 1).trim();
    if (answer.startsWith("new:") && ja && !mem.entities.some((e) => e.kind === "character" && (e.ja === ja || e.vi === ja))) {
      // A name the reader typed: a reader-made card, locked.
      next = {
        ...mem,
        entities: [
          ...mem.entities,
          { ja, vi: ja, kind: "character", status: "locked", knownFrom: pos, evidence: q.evidence.slice(0, 2), history: [{ at: now, vi: ja, status: "locked" }], source: "reader", lastSeen: pos, seen: q.lines },
        ],
      };
    } else if (answer.startsWith("new:")) ja = mem.entities.find((e) => e.kind === "character" && (e.ja === ja || e.vi === ja))!.ja;
    if (ja) next = bindLabel(next, label, ja, "reader");
    return { ...next, asked, updatedAt: now };
  }
  let entities = mem.entities;
  let address = mem.address;
  if (q.kind === "gender" && (answer === "female" || answer === "male")) {
    entities = mem.entities.map((e) => (e.kind === "character" && e.ja === q.who[0].ja ? { ...e, gender: answer, genderBy: "reader" as const, genderSeen: undefined } : e));
  }
  if (q.kind === "pair" && isPairPreset(answer)) {
    const [a, b] = q.who.map((w) => w.vi);
    const { ab, ba } = PAIR_PRESETS[answer];
    address = mem.address.map((r) => ({ ...r }));
    for (const [from, to, terms] of [
      [a, b, ab],
      [b, a, ba],
    ] as const) {
      const r = address.find((x) => x.from === from && x.to === to);
      if (r) {
        r.history = [...(r.history ?? []), { at: now, selfVi: r.selfVi, addressVi: r.addressVi, status: r.status }];
        Object.assign(r, { selfVi: terms[0], addressVi: terms[1], status: "locked", source: "reader", conflicts: undefined });
      } else {
        address.push({ from, to, selfVi: terms[0], addressVi: terms[1], status: "locked", knownFrom: pos, evidence: q.evidence.slice(0, 2), source: "reader", count: 1 });
      }
    }
  }
  return { ...mem, entities, address, asked, updatedAt: now };
}
