/** Pixel box in source-image coordinates. */
export interface Box {
  x: number;
  y: number;
  w: number;
  h: number;
}

export type DetClass = "bubble" | "text_bubble" | "text_free";
/** Label order of ogkalu/comic-text-and-bubble-detector. */
export const DET_CLASSES: readonly DetClass[] = ["bubble", "text_bubble", "text_free"];

export interface Detection {
  cls: DetClass;
  box: Box;
  score: number;
}

export type RegionKind = "bubble" | "free";

export interface TextRegion {
  id: string;
  kind: RegionKind;
  /** Union of the text boxes that belong to this region. */
  box: Box;
  /** Individual detector text boxes; erasure works per member. */
  members: Box[];
  /** Containing speech bubble, when the detector found one. */
  bubble?: Box;
  score: number;
  /** Heuristic reading order (0-based). The model may reorder. */
  order: number;
}

export const ROLES = ["dialogue", "thought", "narration", "sign", "sfx", "decorative", "none"] as const;
export type Role = (typeof ROLES)[number];

export interface RegionTranslation {
  id: string;
  ja: string;
  vi: string;
  role: Role;
  speaker: string;
  to: string;
  style: string[];
  /** Order in which the model emitted this region (its reading order). */
  seq: number;
  /** Deterministic post-fixes that were applied, for transparency. */
  fixes: string[];
}

export type NameKind = "character" | "place" | "org" | "term" | "other";

export interface NameNote {
  ja: string;
  vi: string;
  kind: NameKind;
  evidence: string;
  note?: string;
  /** A character as drawn on this page (gender, age group, hair, clothes), to recognise them on later pages. */
  looks?: string;
  /** Only when the art makes it clear. */
  gender?: "female" | "male";
  /** Where their face is drawn on this page, per-mille [x0, y0, x1, y1]: geometry only, cropped again when needed. */
  face?: [number, number, number, number];
  /** The label this person had on earlier pages before their name was known, e.g. "(boy, curly hair)". */
  was?: string;
}

export interface AddressNote {
  from: string;
  to: string;
  call?: string;
  self_vi?: string;
  address_vi?: string;
  evidence: string;
}

export interface MissedNote {
  ja: string;
  vi: string;
  near?: string;
  role?: Role;
  /** Per-mille page box [x0, y0, x1, y1] from the reader model; refined by a zoomed detection before use. */
  box?: [number, number, number, number];
}

export interface SeriesNote {
  genres: string[];
  tone?: string;
  setting?: string;
}

/** The reader model's request to recall earlier events for lines that refer back to them. */
export interface RecallRequest {
  regions: string[];
  who: string[];
  keys: string[];
}

/** From the recall pass: which earlier event card (c1…) a region refers to. */
export interface PsNote {
  region: string;
  card: string;
  /** Short Vietnamese name of the earlier event. */
  label?: string;
}

export interface PageNotes {
  names: NameNote[];
  address: AddressNote[];
  missed: MissedNote[];
  /** Only on the first page of a story without a profile (cold start). */
  series?: SeriesNote;
  recall?: RecallRequest;
  ps?: PsNote[];
}

/** A translator's "P/S": a line refers to an earlier event; where to re-read it. */
export interface RecallNote {
  regionId: string;
  /** Ready to show, e.g. "P/S: lời hứa ở lễ hội — chương 3, trang 12." */
  text: string;
  label: string;
  chapter: number;
  page: number;
  pageId: string;
  /** The L1 card it comes from. */
  event: string;
}

export interface RecallInfo {
  /** What the reader model asked for. */
  request: RecallRequest;
  /** Cards found before the reading position. */
  cards: number;
  /** Regions whose translation the recall pass revised. */
  revised: string[];
  notes: RecallNote[];
  ms: number;
  costUsd: number;
}

export interface Usage {
  promptTokens?: number;
  completionTokens?: number;
  /** Prompt tokens served from the provider's prompt cache. */
  cachedTokens?: number;
  costUsd?: number;
}

export interface PageTimings {
  detectMs: number;
  /** From sending the model request to the first streamed byte. */
  ttfbMs?: number;
  /** From the start of the page job to the first finished region. */
  firstRegionMs?: number;
  /** Crop OCR of every region before the model call ("OCR first" reading). */
  ocrMs?: number;
  totalMs: number;
}

export interface ReadingPosition {
  chapter: number;
  page: number;
}

export interface PageResult {
  pageId: string;
  seriesId: string;
  position: ReadingPosition;
  image: { w: number; h: number };
  regions: TextRegion[];
  translations: Record<string, RegionTranslation>;
  notes: PageNotes;
  model: string;
  promptVersion: string;
  timings: PageTimings;
  usage: Usage;
  /** Region ids the model never returned (after the bounded repair). */
  missingIds: string[];
  /** Region ids recovered by the repair request. */
  repairedIds: string[];
  /** Present when the page referred back to earlier events (prompt v4). */
  recall?: RecallInfo;
  createdAt: string;
}

/** A reconstructed background for one region: a transparent PNG with only the hole painted. */
export interface PatchData {
  id: string;
  x: number;
  y: number;
  w: number;
  h: number;
  /** Kept in memory only, never written to disk. */
  dataUrl: string;
  coverage: number;
  ms: number;
  /** Text boxes the hole was built from (tighter than the region box for small free text). */
  textBoxes: Box[];
  /** Bounds of the glyph strokes that were removed: where the original text really sat. */
  textExtent?: Box;
  /** Colour of the source glyph strokes, when they could be isolated. */
  ink?: [number, number, number];
  /** One clean tone around the source strokes (an outline or a flat background), when there was one. */
  outline?: [number, number, number];
  /** Pictures inside the text boxes that were kept (a photo on a card): lettering keeps off them. */
  keepOut?: Box[];
  /** Inpainter that redrew the art. */
  engine?: "migan" | "lama";
}

export type TranslateEvent =
  | { type: "detected"; pageId: string; image: { w: number; h: number }; regions: TextRegion[]; detectMs: number }
  | { type: "region"; t: RegionTranslation; atMs: number }
  | { type: "notes"; notes: PageNotes }
  /** Text the reader model found outside every detected region, located and added after the page. */
  | { type: "regions-added"; regions: TextRegion[] }
  /** Backgrounds reconstructed while the page was being translated (image data, never stored). */
  | { type: "patches"; patches: PatchData[]; ms: number; kept?: string[] }
  /** P/S notes for lines that refer back to earlier events (after the recall pass revised them). */
  | { type: "recall"; notes: RecallNote[] }
  | { type: "done"; result: PageResult }
  | { type: "error"; message: string; code?: string };
