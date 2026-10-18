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
}

export interface PageNotes {
  names: NameNote[];
  address: AddressNote[];
  missed: MissedNote[];
}

export interface Usage {
  promptTokens?: number;
  completionTokens?: number;
  costUsd?: number;
}

export interface PageTimings {
  detectMs: number;
  /** From sending the model request to the first streamed byte. */
  ttfbMs?: number;
  /** From the start of the page job to the first finished region. */
  firstRegionMs?: number;
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
  createdAt: string;
}

export type TranslateEvent =
  | { type: "detected"; pageId: string; image: { w: number; h: number }; regions: TextRegion[]; detectMs: number }
  | { type: "region"; t: RegionTranslation; atMs: number }
  | { type: "notes"; notes: PageNotes }
  | { type: "done"; result: PageResult }
  | { type: "error"; message: string; code?: string };
