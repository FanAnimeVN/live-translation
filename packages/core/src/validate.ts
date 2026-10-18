import { z } from "zod";
import { ROLES, type NameKind, type PageNotes, type RegionTranslation, type Role } from "./types";

const str = z.preprocess((v) => (v == null ? "" : typeof v === "string" ? v : String(v)), z.string());

const RegionLine = z.object({
  id: str,
  ja: str.optional(),
  vi: str.optional(),
  role: str.optional(),
  speaker: str.optional(),
  to: str.optional(),
  addressee: str.optional(),
  style: z.array(str).optional(),
});

const NAME_KINDS: NameKind[] = ["character", "place", "org", "term", "other"];

const NotesLine = z.object({
  type: z.literal("notes"),
  names: z
    .array(z.object({ ja: str, vi: str, kind: str.optional(), evidence: str.optional(), note: str.optional() }))
    .optional(),
  address: z
    .array(
      z.object({
        from: str,
        to: str,
        call: str.optional(),
        self_vi: str.optional(),
        address_vi: str.optional(),
        evidence: str.optional(),
      }),
    )
    .optional(),
  missed: z.array(z.object({ ja: str, vi: str.optional(), near: str.optional() })).optional(),
});

export function isNotesObject(value: unknown): boolean {
  return typeof value === "object" && value !== null && (value as { type?: unknown }).type === "notes";
}

/** Validate one streamed region object; unknown ids and malformed objects are rejected. */
export function parseRegionObject(value: unknown, validIds: ReadonlySet<string>, seq: number): RegionTranslation | null {
  const parsed = RegionLine.safeParse(value);
  if (!parsed.success) return null;
  const v = parsed.data;
  const id = v.id.trim();
  if (!validIds.has(id)) return null;
  const role = (ROLES as readonly string[]).includes(v.role ?? "") ? (v.role as Role) : "dialogue";
  const ja = (v.ja ?? "").trim();
  let vi = (v.vi ?? "").trim();
  const fixes: string[] = [];
  const stacked = fixHonorificStacking(vi);
  if (stacked.text !== vi) {
    vi = stacked.text;
    fixes.push("honorific-no-stack");
  }
  return {
    id,
    ja,
    vi,
    role: ja || vi ? role : "none",
    speaker: clean(v.speaker),
    to: clean(v.to ?? v.addressee),
    style: (v.style ?? []).map((s) => s.trim()).filter(Boolean),
    seq,
    fixes,
  };
}

export function parseNotesObject(value: unknown): PageNotes | null {
  const parsed = NotesLine.safeParse(value);
  if (!parsed.success) return null;
  const n = parsed.data;
  return {
    names: (n.names ?? [])
      .filter((x) => x.ja.trim() && x.vi.trim())
      .map((x) => ({
        ja: x.ja.trim(),
        vi: x.vi.trim(),
        kind: (NAME_KINDS as string[]).includes(x.kind ?? "") ? (x.kind as NameKind) : "other",
        evidence: (x.evidence ?? "").trim(),
        note: x.note?.trim() || undefined,
      })),
    address: (n.address ?? [])
      .filter((x) => x.from.trim() && x.to.trim())
      .map((x) => ({
        from: x.from.trim(),
        to: x.to.trim(),
        call: x.call?.trim() || undefined,
        self_vi: x.self_vi?.trim() || undefined,
        address_vi: x.address_vi?.trim() || undefined,
        evidence: (x.evidence ?? "").trim(),
      })),
    missed: (n.missed ?? [])
      .filter((x) => x.ja.trim())
      .map((x) => ({ ja: x.ja.trim(), vi: (x.vi ?? "").trim(), near: x.near?.trim() || undefined })),
  };
}

const clean = (s: string | undefined) => {
  const t = (s ?? "").trim();
  return t && !/^(unknown|không rõ|n\/a|none|\?)$/i.test(t) ? t : "unknown";
};

// A retained sibling vocative already carries its title. Remove a Vietnamese
// kinship word stacked directly in front of it ("chị nee-chan" -> "nee-chan").
// A comma breaks the stack ("anh, onii-chan" stays: there "anh" is a pronoun).
const SIBLING_VOCATIVE = String.raw`(?:o?nee|o?nii)-(?:chan|san|sama|chama)`;
const STACK = new RegExp(
  String.raw`(^|[\s"“'‘(\[«…—-])(chị\s+gái|chị|anh\s+trai|anh)\s+(${SIBLING_VOCATIVE})(?=$|[\s,.!?…~"”'’)\]»:;-])`,
  "giu",
);

export function fixHonorificStacking(text: string): { text: string; count: number } {
  let count = 0;
  const out = text.replace(STACK, (_m, lead: string, title: string, vocative: string) => {
    count++;
    const capital = title[0] !== title[0].toLowerCase();
    const v = capital ? vocative[0].toUpperCase() + vocative.slice(1) : vocative;
    return lead + v;
  });
  return { text: out, count };
}
