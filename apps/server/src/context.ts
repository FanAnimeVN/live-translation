/**
 * Context management that runs off the critical path:
 *  - optional series metadata (AniList) → a translation profile, confirmed by the reader;
 *  - background memory updates (story so far, relationships, address matrix) on a cheap
 *    text model every few pages.
 * Nothing here blocks a page translation, and nothing is dated after what was read.
 */
import {
  applyMemoryUpdate,
  backgroundInput,
  JsonObjectStream,
  type MemoryUpdate,
  type MetaCharacter,
  type ReadingPosition,
  type SeriesMemory,
  type SeriesProfile,
} from "@lt/core";
import { streamChat } from "./openrouter";

/** Cheap text model for background work (summaries, profiles). */
export const BACKGROUND_MODEL = process.env.BACKGROUND_MODEL ?? "deepseek/deepseek-v4.1-flash";
/** Summarize once this many dialogue lines have been read since the last update. */
export const UPDATE_EVERY_LINES = 24;

// ---------------------------------------------------------------- AniList

const ANILIST = "https://graphql.anilist.co";

export interface SeriesCandidate {
  id: number;
  title: { romaji?: string; english?: string; native?: string };
  synonyms: string[];
  genres: string[];
  url: string;
  similarity: number;
}

async function anilist<T>(query: string, variables: Record<string, unknown>): Promise<T> {
  const res = await fetch(ANILIST, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ query, variables }),
  });
  if (!res.ok) throw new Error(`AniList ${res.status}`);
  const body = (await res.json()) as { data?: T; errors?: Array<{ message: string }> };
  if (body.errors?.length) throw new Error(`AniList: ${body.errors[0].message}`);
  return body.data as T;
}

const norm = (s: string) => s.normalize("NFKC").toLowerCase().replace(/[^\p{L}\p{N}]+/gu, "");

/** Character-bigram Dice similarity, robust to punctuation and spacing differences. */
export function titleSimilarity(a: string, b: string): number {
  const x = norm(a);
  const y = norm(b);
  if (!x || !y) return 0;
  if (x === y) return 1;
  const grams = (s: string) => {
    const m = new Map<string, number>();
    for (let i = 0; i < s.length - 1; i++) m.set(s.slice(i, i + 2), (m.get(s.slice(i, i + 2)) ?? 0) + 1);
    return m;
  };
  const gx = grams(x);
  const gy = grams(y);
  let inter = 0;
  for (const [g, n] of gx) inter += Math.min(n, gy.get(g) ?? 0);
  return (2 * inter) / Math.max(1, x.length - 1 + y.length - 1);
}

/**
 * Search candidates for the reader to confirm. Adult titles are excluded and every
 * candidate carries a title similarity: fuzzy search alone returns unrelated works.
 */
export async function searchSeries(title: string): Promise<SeriesCandidate[]> {
  const data = await anilist<{ Page: { media: Array<Omit<SeriesCandidate, "similarity" | "url"> & { siteUrl: string }> } }>(
    `query($s:String){Page(perPage:6){media(search:$s,type:MANGA,isAdult:false){id title{romaji english native} synonyms genres siteUrl}}}`,
    { s: title },
  );
  return data.Page.media
    .map((m) => ({
      id: m.id,
      title: m.title,
      synonyms: m.synonyms ?? [],
      genres: m.genres ?? [],
      url: m.siteUrl,
      similarity: Math.max(...[m.title.romaji, m.title.english, m.title.native, ...(m.synonyms ?? [])].filter(Boolean).map((t) => titleSimilarity(title, t!))),
    }))
    .sort((a, b) => b.similarity - a.similarity);
}

/** Remove AniList spoiler blocks (~!…!~), HTML and source notes; keep it short. */
export function stripSpoilers(text: string | null | undefined, max = 400): string {
  return (text ?? "")
    .replace(/~![\s\S]*?!~/g, "")
    .replace(/<br\s*\/?>/gi, " ")
    .replace(/<[^>]+>/g, "")
    .replace(/\(Source:[^)]*\)/gi, "")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, max);
}

interface MediaDetail {
  id: number;
  title: { romaji?: string; english?: string; native?: string };
  siteUrl: string;
  genres: string[];
  description: string | null;
  tags: Array<{ name: string; rank: number; isMediaSpoiler: boolean; isGeneralSpoiler: boolean }>;
  characters: { edges: Array<{ role: string; node: { name: { full: string; native: string | null; alternative: string[] }; gender: string | null; description: string | null } }> };
}

export async function fetchSeries(id: number): Promise<MediaDetail> {
  const data = await anilist<{ Media: MediaDetail }>(
    `query($id:Int){Media(id:$id,type:MANGA){id title{romaji english native} siteUrl genres description(asHtml:false)
      tags{name rank isMediaSpoiler isGeneralSpoiler}
      characters(perPage:25,sort:[ROLE,RELEVANCE]){edges{role node{name{full native alternative} gender description(asHtml:false)}}}}}`,
    { id },
  );
  return data.Media;
}

// ---------------------------------------------------------------- cheap text model

/** Most background models can skip reasoning; some endpoints refuse to (measured 2026-10-19). */
const MANDATORY_REASONING = /^z-ai\/glm-5/;

async function jsonCall<T>(system: string, user: string, purpose: string, model = BACKGROUND_MODEL): Promise<{ value: T | null; costUsd: number; ms: number }> {
  let value: T | null = null;
  const parser = new JsonObjectStream((v) => {
    value ??= v as T;
  });
  const stats = await streamChat({
    model,
    system,
    parts: [{ type: "text", text: user }],
    purpose,
    maxTokens: MANDATORY_REASONING.test(model) ? 4000 : 1800,
    // Nobody waits on this call: cheapest provider, as little reasoning as the model allows.
    sort: "price",
    extra: { reasoning: MANDATORY_REASONING.test(model) ? { effort: "low" } : { enabled: false } },
    onText: (d) => parser.push(d),
  });
  return { value, costUsd: stats.costUsd, ms: Math.round(stats.totalMs) };
}

const PROFILE_SYSTEM = `You prepare a translation profile for a Japanese→Vietnamese manga translator from PUBLIC, spoiler-stripped series metadata.
Use only facts present in the metadata. No twists, no future events, no guesses about relationships that are not stated.
Return one JSON object:
{"genres":["…"],"tone":"short English","setting":"short English","register":"English, ≤ 60 words: how Vietnamese pronouns and formality should work in THIS story's world (peers, family, superiors, era), and keep Japanese honorifics in romaji",
 "synopsis":"premise only, ≤ 50 words, English",
 "characters":[{"native":"exact native name from the metadata","speech":"self-pronoun and speaking style if stated, else omit","relations":["short non-spoiler facts stated in the metadata"]}]}`;

/** Build the series profile and character hints once, from confirmed metadata. */
export async function bootstrapFromMetadata(mem: SeriesMemory, id: number): Promise<{ memory: SeriesMemory; costUsd: number; ms: number }> {
  const m = await fetchSeries(id);
  const tags = m.tags.filter((t) => t.rank >= 60 && !t.isMediaSpoiler && !t.isGeneralSpoiler).map((t) => t.name).slice(0, 10);
  const characters: MetaCharacter[] = m.characters.edges.map((e) => ({
    native: e.node.name.native ?? "",
    full: e.node.name.full,
    alternative: e.node.name.alternative ?? [],
    gender: e.node.gender ?? undefined,
    role: e.role,
    description: stripSpoilers(e.node.description, 300),
  }));
  const user = JSON.stringify({
    title: m.title,
    genres: m.genres,
    tags,
    synopsis: stripSpoilers(m.description, 700),
    characters: characters.slice(0, 15).map((c) => ({ native: c.native, name: c.full, gender: c.gender, role: c.role, description: c.description })),
  });
  const { value, costUsd, ms } = await jsonCall<SeriesProfile & { characters?: Array<{ native: string; speech?: string; relations?: string[] }> }>(
    PROFILE_SYSTEM,
    user,
    "series-profile",
  );
  const hints = new Map((value?.characters ?? []).map((c) => [c.native, c]));
  const profile: SeriesProfile = {
    genres: value?.genres?.length ? value.genres : m.genres,
    tone: value?.tone,
    setting: value?.setting,
    register: value?.register,
    synopsis: value?.synopsis ?? stripSpoilers(m.description, 300),
    source: "metadata",
  };
  return {
    memory: {
      ...mem,
      profile,
      metadata: {
        source: "anilist",
        id: m.id,
        title: m.title.romaji ?? m.title.native ?? "",
        url: m.siteUrl,
        characters: characters.map((c) => ({ ...c, speech: hints.get(c.native)?.speech, relations: hints.get(c.native)?.relations })),
        fetchedAt: new Date().toISOString(),
      },
      updatedAt: new Date().toISOString(),
    },
    costUsd,
    ms,
  };
}

const UPDATE_SYSTEM = `You maintain a spoiler-safe story memory for a manga being translated from Japanese to Vietnamese.
You receive the current memory and NEW dialogue the reader has just read: ja = source, vi = draft translation, speaker→listener when known, ids PAGE:REGION.
Update the memory ONLY from what these lines and the existing memory establish. A question is not a fact, a request is not a completed action, a worry is not an event. Never guess future events, identities, genders or relationships: unknown stays unknown.
- Attribute a line or an action to a character only when its speaker field names them; lines from "unknown" stay unattributed ("someone says…").
- Characters: only those who speak or are named in the NEW dialogue; never add genders, ages or relations the lines do not show (keep what the memory already has).
- Self-pronouns (俺, 私, あたし, ボク) describe the speaker's style, they are not how the speaker calls someone.
- Keep the direction of relations: "A is B's owner" is not "B is A's owner".
Return one JSON object:
{"story_so_far":"Vietnamese, ≤ 120 words, the whole story up to now (merge with the previous one)",
 "segment":"Vietnamese, ≤ 60 words: only what the NEW dialogue adds (kept in the archive as is)",
 "events":[{"text":"Vietnamese, one line","evidence":["PAGE:REGION"]}],
 "characters":[{"name":"exact name used in the memory","ja":"…","gender":"female|male|unknown","role":"short English","speech":"self-pronoun + style, short","relations":["short English facts"]}],
 "address":[{"from":"name","to":"name","call":"Japanese vocative if any","self_vi":"…","address_vi":"…","evidence":["PAGE:REGION"]}]}
At most 4 events, 6 characters, 6 address rules. Use names exactly as written in the memory.`;

export interface PlannedUpdate {
  update: MemoryUpdate | null;
  upTo: ReadingPosition;
  /** pageId:regionId of the pending lines this update covered. */
  covered: Set<string>;
  costUsd: number;
  ms: number;
}

/**
 * Summarize the dialogue read since the last update with a cheap model. The caller
 * applies the result to the freshest memory (pages may have been read meanwhile).
 * Returns null when there is not enough new dialogue yet.
 */
export async function planMemoryUpdate(mem: SeriesMemory, force = false, model = BACKGROUND_MODEL): Promise<PlannedUpdate | null> {
  const pending = mem.pending ?? [];
  if (!pending.length || (!force && pending.length < UPDATE_EVERY_LINES)) return null;
  const upTo: ReadingPosition = pending.reduce((a, l) => (l.pos.chapter > a.chapter || (l.pos.chapter === a.chapter && l.pos.page > a.page) ? l.pos : a), pending[0].pos);
  // Bounded whatever the length of the series: rolling story + the cast this dialogue involves.
  const current = backgroundInput(mem);
  const dialogue = pending.map((l) => `${l.pageId}:${l.regionId} [${l.speaker}${l.to && l.to !== "unknown" ? `→${l.to}` : ""}] ${l.ja} => ${l.vi}`).join("\n");
  const { value, costUsd, ms } = await jsonCall<MemoryUpdate>(
    UPDATE_SYSTEM,
    `CURRENT MEMORY:\n${JSON.stringify(current)}\n\nNEW DIALOGUE:\n${dialogue}`,
    "memory-update",
    model,
  );
  return { update: value, upTo, covered: new Set(pending.map((l) => `${l.pageId}:${l.regionId}`)), costUsd, ms };
}

/** Apply a planned update to the current memory, keeping lines read while it ran. */
export function applyPlanned(fresh: SeriesMemory, plan: PlannedUpdate): SeriesMemory {
  if (!plan.update) return fresh;
  const keep = (fresh.pending ?? []).filter((l) => !plan.covered.has(`${l.pageId}:${l.regionId}`));
  return applyMemoryUpdate(fresh, plan.update, plan.upTo, BACKGROUND_MODEL, keep);
}
