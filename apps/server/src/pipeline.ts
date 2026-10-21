import { writeFile } from "node:fs/promises";
import { join } from "node:path";
import {
  activeNames,
  applyRegionRules,
  area,
  atOrBefore,
  buildUserParts,
  center,
  clampBox,
  containment,
  containsPoint,
  expand,
  fromPermille,
  iou,
  roundBox,
  type MissedNote,
  isNotesObject,
  JsonObjectStream,
  stableContext,
  volatileContext,
  parseNotesObject,
  parseRegionObject,
  PROMPT_VERSION,
  SYSTEM_PROMPT,
  RECALL_SYSTEM,
  buildRecallParts,
  recallContext,
  recallEvents,
  RECALL_MIN_CHAPTERS,
  psWorthy,
  type PsNote,
  type RecallInfo,
  type VolatileOptions,
  type PageNotes,
  type PageResult,
  type ReadingPosition,
  type RegionTranslation,
  type SeriesMemory,
  type TextRegion,
  type TranslateEvent,
} from "@lt/core";
import { detect, detectInCrop } from "./detector";
import { decodeImage, faceCrop, markedPageDataUrl, regionCrops, type DecodedPage } from "./image";
import { readRegions } from "./ocr";
import { mockReply } from "./mock";
import { streamChat } from "./openrouter";
import { PRIVATE_DIR } from "./env";

export interface PageInput {
  id: string;
  title: string;
  seriesId: string;
  position: ReadingPosition;
  bytes: Buffer;
}

/** Detector confidence needed before a text the model reported outside every region is lettered in place. */
const MISSED_MIN_SCORE = 0.4;

export interface TranslateOptions {
  model: string;
  memory: SeriesMemory;
  emit?: (e: TranslateEvent) => void;
  signal?: AbortSignal;
  /** Attach zoomed crops: "small" regions only (default), "all" or "none". */
  crops?: "small" | "all" | "none";
  /** Request fields applied after the model's defaults (e.g. a reasoning setting under test). */
  extra?: Record<string, unknown>;
  /** Called once regions are known, before the model call: work that needs no translation starts here. */
  onDetected?: (page: DecodedPage, regions: TextRegion[]) => void;
  /** L0 size and budget overrides (the K experiment); defaults come from the memory module. */
  context?: VolatileOptions & { volatileTokens?: number };
  /** Revise lines that refer back to earlier events with recalled cards (default on). */
  recall?: boolean;
  /** Another page prompt, for A/B runs of prompt versions (tools/eval/src/bakeoff.ts --system-file). */
  systemPrompt?: string;
  /**
   * Bytes of a page already read, by id: lets the request show the faces of the characters in the
   * scene (cropped from the box the memory kept). Omitted → no face references.
   */
  refImage?: (pageId: string) => Promise<Buffer | undefined>;
  /**
   * How the model gets the text (docs/LOCAL-MODELS.md §1): "image" (it reads the page image, default),
   * "ocr+image" (a crop OCR reads every region first and the page image is still sent) or "ocr" (OCR text
   * plus face references only: ~25% cheaper and the first token ~4x sooner on Haiku 5.5, 25 pages) or
   * "ocr+thumb" (OCR text plus the marked page at 640 px, ~300 image tokens: who is drawn speaking).
   * Measured 22/10 (Haiku 5.5, 25 pages, 1 run each; docs/LOCAL-MODELS.md §1): ocr+thumb keeps the image
   * mode's speakers (5% unknown against 35% for OCR text alone) at ~23% lower cost, with lower CER and higher
   * chrF. Default: READING_MODE in the environment, else "ocr+thumb"; without the OCR model files the page
   * falls back to image reading.
   */
  reading?: ReadingMode;
}

export type ReadingMode = "image" | "ocr+image" | "ocr+thumb" | "ocr";

/** Long side of the page thumbnail sent with OCR text in "ocr+thumb" reading. */
const THUMB_SIDE = 640;
const DEFAULT_READING = (process.env.READING_MODE as ReadingMode | undefined) ?? "ocr+thumb";
let ocrMissingWarned = false;

/** Face references per request: ~25 image tokens each on Claude at 128 px. */
const MAX_FACE_REFS = 6;

/** Characters most likely on this page (active in the latest dialogue first) whose face the memory located. */
async function faceReferences(p: PageInput, o: TranslateOptions): Promise<Array<{ name: string; ja: string; dataUrl: string }>> {
  if (!o.refImage) return [];
  const active = activeNames(o.memory, p.position);
  const chars = o.memory.entities
    .filter((e) => e.kind === "character" && e.ref && e.ref.pageId !== p.id && e.status !== "rejected" && atOrBefore(e.knownFrom, p.position))
    .sort((a, b) => Number(active.has(b.vi)) - Number(active.has(a.vi)) || (b.seen ?? 1) - (a.seen ?? 1))
    .slice(0, MAX_FACE_REFS);
  const pages = new Map<string, DecodedPage | undefined>();
  const out: Array<{ name: string; ja: string; dataUrl: string }> = [];
  for (const e of chars) {
    const id = e.ref!.pageId;
    if (!pages.has(id)) {
      const bytes = await o.refImage(id).catch(() => undefined);
      pages.set(id, bytes ? await decodeImage(bytes) : undefined);
    }
    const d = pages.get(id);
    if (d) out.push({ name: e.vi, ja: e.ja, dataUrl: await faceCrop(d, e.ref!.box) });
  }
  return out;
}

/**
 * One page: detect regions → one streamed vision request that reads and translates
 * every region in context → one bounded repair for ids the model skipped.
 */
export async function translatePage(page: PageInput, opts: TranslateOptions): Promise<PageResult> {
  const t0 = performance.now();
  const emit = opts.emit ?? (() => {});
  const decoded = await decodeImage(page.bytes);
  const det = await detect(decoded);
  const regions = det.regions;
  emit({ type: "detected", pageId: page.id, image: { w: decoded.w, h: decoded.h }, regions, detectMs: det.ms });
  opts.onDetected?.(decoded, regions);

  const reading = opts.reading ?? DEFAULT_READING;
  const tOcr = performance.now();
  let preRead: Record<string, string> | undefined;
  if (reading !== "image" && regions.length && !opts.model.startsWith("mock/")) {
    try {
      preRead = await readRegions(decoded, regions);
    } catch (e) {
      // No OCR model on this machine (models/ocr/baberu): read from the image as before.
      if (!ocrMissingWarned) console.warn(`OCR unavailable, reading pages from the image: ${(e as Error).message}`);
      ocrMissingWarned = true;
    }
  }
  const ocrMs = preRead ? Math.round(performance.now() - tOcr) : undefined;

  const translations: Record<string, RegionTranslation> = {};
  const notes: PageNotes = { names: [], address: [], missed: [] };
  const usage = { promptTokens: 0, completionTokens: 0, cachedTokens: 0, costUsd: 0 };
  let firstRegionMs: number | undefined;
  let ttfbMs: number | undefined;
  let seq = 0;

  const run = async (onlyIds?: string[]) => {
    const ids = new Set((onlyIds ?? regions.map((r) => r.id)).filter((id) => !translations[id]));
    const keepRecall = notes.recall;
    const parser = new JsonObjectStream((value) => {
      if (isNotesObject(value)) {
        const n = parseNotesObject(value);
        if (n) {
          notes.names.push(...n.names);
          notes.address.push(...n.address);
          notes.missed.push(...n.missed);
          notes.recall = keepRecall ?? n.recall;
          emit({ type: "notes", notes: n });
        }
        return;
      }
      const parsed = parseRegionObject(value, ids, seq);
      if (!parsed || translations[parsed.id]) return;
      const t = applyRegionRules(parsed, regions.find((r) => r.id === parsed.id));
      seq++;
      translations[t.id] = t;
      firstRegionMs ??= performance.now() - t0;
      emit({ type: "region", t, atMs: Math.round(performance.now() - t0) });
    });
    if (opts.model.startsWith("mock/")) {
      const t1 = performance.now();
      for await (const chunk of mockReply(regions, onlyIds)) {
        ttfbMs ??= performance.now() - t1;
        parser.push(chunk);
      }
      return;
    }
    let raw = "";
    const stats = await streamChat({
      model: opts.model,
      system: opts.systemPrompt ?? SYSTEM_PROMPT,
      parts: await requestParts(page, decoded, regions, opts, onlyIds, preRead, reading),
      purpose: onlyIds ? "repair" : "translate-page",
      pageId: page.id,
      signal: opts.signal,
      extra: opts.extra,
      onText: (d) => {
        if (process.env.LT_DUMP_RAW) raw += d;
        parser.push(d);
      },
    });
    // Dev aid for models that do not follow the format (LT_DUMP_RAW=1): the raw reply, private.
    if (process.env.LT_DUMP_RAW) await writeFile(join(PRIVATE_DIR, `raw-${opts.model.replace(/[^\w.-]/g, "_")}-${page.id}${onlyIds ? "-repair" : ""}.txt`), raw, "utf8");
    ttfbMs ??= stats.ttfbMs;
    usage.promptTokens += stats.promptTokens ?? 0;
    usage.completionTokens += stats.completionTokens ?? 0;
    usage.cachedTokens += stats.cachedTokens ?? 0;
    usage.costUsd += stats.costUsd;
  };

  if (regions.length) await run();
  let missing = regions.map((r) => r.id).filter((id) => !translations[id]);
  const repairedIds: string[] = [];
  if (missing.length && missing.length < regions.length) {
    const before = new Set(Object.keys(translations));
    await run(missing);
    repairedIds.push(...missing.filter((id) => translations[id] && !before.has(id)));
    missing = missing.filter((id) => !translations[id]);
  }

  // Text the model saw outside every region (name tags, captions): place what a zoomed
  // detection confirms; the rest stays a note the reader can open, never erased blindly.
  const placed = await placeMissed(decoded, regions, notes.missed);
  if (placed.length) {
    emit({ type: "regions-added", regions: placed.map((p) => p.region) });
    for (const p of placed) {
      const t: RegionTranslation = { id: p.region.id, ja: p.note.ja, vi: p.note.vi, role: p.note.role ?? "sign", speaker: "unknown", to: "unknown", style: [], seq: seq++, fixes: ["placed-missed"] };
      translations[t.id] = t;
      emit({ type: "region", t, atMs: Math.round(performance.now() - t0) });
    }
    notes.missed = notes.missed.filter((m) => !placed.some((p) => p.note === m));
  }

  const recall = await recallPass();

  const result: PageResult = {
    pageId: page.id,
    seriesId: page.seriesId,
    position: page.position,
    image: { w: decoded.w, h: decoded.h },
    regions: [...regions, ...placed.map((p) => p.region)],
    translations,
    notes,
    model: opts.model,
    promptVersion: opts.systemPrompt ? "custom" : PROMPT_VERSION,
    timings: {
      detectMs: Math.round(det.ms),
      ttfbMs: ttfbMs === undefined ? undefined : Math.round(ttfbMs),
      firstRegionMs: firstRegionMs === undefined ? undefined : Math.round(firstRegionMs),
      ...(ocrMs !== undefined ? { ocrMs } : {}),
      totalMs: Math.round(performance.now() - t0),
    },
    usage,
    missingIds: missing,
    repairedIds,
    ...(recall ? { recall } : {}),
    createdAt: new Date().toISOString(),
  };
  emit({ type: "done", result });
  return result;

  /**
   * Lines the reader model flagged as referring back to earlier events: look up L1 cards
   * written before this page, and when some match, run one small text-only pass over just
   * those lines with the cards attached. P/S notes come only from cards the pass cites.
   */
  async function recallPass(): Promise<RecallInfo | undefined> {
    const request = notes.recall;
    if (!request || opts.recall === false || opts.model.startsWith("mock/")) return undefined;
    const t1 = performance.now();
    const info: RecallInfo = { request, cards: 0, revised: [], notes: [], ms: 0, costUsd: 0 };
    const ids = request.regions.filter((id) => translations[id] && translations[id].role !== "none");
    const cards = ids.length
      ? recallEvents(opts.memory, page.position, { who: request.who, keys: request.keys, text: ids.map((id) => translations[id].ja).join(" "), minChaptersBack: RECALL_MIN_CHAPTERS }, 4)
      : [];
    info.cards = cards.length;
    if (!cards.length) {
      info.ms = Math.round(performance.now() - t1);
      return info;
    }
    const ps: PsNote[] = [];
    const valid = new Set(ids);
    const parser = new JsonObjectStream((value) => {
      if (isNotesObject(value)) {
        ps.push(...(parseNotesObject(value)?.ps ?? []));
        return;
      }
      const t = parseRegionObject(value, valid, 0);
      const prev = t && translations[t.id];
      if (!t || !prev || !t.vi || t.vi === prev.vi) return;
      // Only the Vietnamese may change: the source reading, role, speaker and listener were read
      // from the image, which this text-only pass never sees.
      translations[t.id] = { ...prev, vi: t.vi, fixes: [...prev.fixes, ...t.fixes, "recall"] };
      if (!info.revised.includes(t.id)) info.revised.push(t.id);
      emit({ type: "region", t: translations[t.id], atMs: Math.round(performance.now() - t0) });
    });
    const order = Object.values(translations).sort((a, b) => a.seq - b.seq);
    const stats = await streamChat({
      model: opts.model,
      system: RECALL_SYSTEM,
      parts: buildRecallParts({
        title: page.title,
        position: page.position,
        lines: order.filter((t) => t.role !== "none").map((t) => ({ id: t.id, speaker: t.speaker, to: t.to, ja: t.ja, vi: t.vi, role: t.role })),
        ids,
        cards: recallContext(cards),
        stableMemory: stableContext(opts.memory, page.position),
      }),
      purpose: "recall",
      pageId: page.id,
      signal: opts.signal,
      maxTokens: 1200,
      onText: (d) => parser.push(d),
    });
    usage.promptTokens += stats.promptTokens ?? 0;
    usage.completionTokens += stats.completionTokens ?? 0;
    usage.cachedTokens += stats.cachedTokens ?? 0;
    usage.costUsd += stats.costUsd;
    info.costUsd = stats.costUsd;
    // A P/S only for an important event dozens of chapters back, and one per page at most:
    // the cited card with the highest importance, then the oldest.
    const cited = ps
      .map((p) => ({ p, c: cards[Number(p.card.replace(/^c/i, "")) - 1] }))
      .filter(({ p, c }) => c && valid.has(p.region) && psWorthy(c, page.position))
      .sort((a, b) => (b.c.event.importance ?? 1) - (a.c.event.importance ?? 1) || a.c.at.chapter - b.c.at.chapter)
      .slice(0, 1);
    for (const { p, c } of cited) {
      const label = (p.label || c.event.text).replace(/[.。]+$/, "").slice(0, 80);
      info.notes.push({
        regionId: p.region,
        label,
        chapter: c.at.chapter,
        page: c.at.page,
        pageId: c.pageId,
        event: c.event.text,
        text: `P/S: ${label} — chương ${c.at.chapter}, trang ${c.at.page}.`,
      });
    }
    if (info.notes.length) emit({ type: "recall", notes: info.notes });
    info.ms = Math.round(performance.now() - t1);
    return info;
  }

  async function placeMissed(d: DecodedPage, rs: TextRegion[], missed: MissedNote[]): Promise<Array<{ region: TextRegion; note: MissedNote }>> {
    const out: Array<{ region: TextRegion; note: MissedNote }> = [];
    const taken = rs.map((r) => r.bubble ?? r.box);
    for (const note of missed) {
      if (!note.box || !note.vi || note.role === "sfx" || note.role === "decorative" || note.role === "none") continue;
      const rough = fromPermille(note.box, d.w, d.h);
      const size = Math.max(rough.w, rough.h);
      const search = roundBox(clampBox(expand(rough, Math.max(16, size * 0.6)), d.w, d.h));
      // Lettering an added region erases what is under it, so the model's rough box is only a
      // hint: the detector must find confident text right there, of about that size. Otherwise
      // the note stays a note and the art is left alone (a wrong box once erased screentone and
      // a character's face while the real text, a little to the side, stayed).
      const near = expand(rough, size * 0.15);
      const best = (await detectInCrop(d, search, MISSED_MIN_SCORE))
        .filter((c) => {
          const ratio = area(c.box) / Math.max(1, area(rough));
          return ratio >= 0.2 && ratio <= 5 && (iou(c.box, rough) >= 0.2 || containsPoint(near, center(c.box)));
        })
        .filter((c) => !taken.some((t) => containment(c.box, t) > 0.5 || containment(t, c.box) > 0.5))
        .sort((a, b) => iou(b.box, rough) - iou(a.box, rough) || b.score - a.score)[0];
      if (!best) continue;
      taken.push(best.box);
      const k = out.length + 1;
      out.push({ region: { id: `m${k}`, kind: "free", box: best.box, members: [best.box], score: Math.round(best.score * 1000) / 1000, order: rs.length + k - 1 }, note });
    }
    return out;
  }

  async function requestParts(p: PageInput, d: DecodedPage, rs: TextRegion[], o: TranslateOptions, onlyIds?: string[], preRead?: Record<string, string>, mode: ReadingMode = "image") {
    const cropIds = o.crops === "all" ? rs.map((r) => r.id) : o.crops === "none" ? [] : undefined;
    const withImage = mode !== "ocr" || !preRead;
    const thumb = mode === "ocr+thumb" && !!preRead;
    return buildUserParts({
      title: p.title,
      position: p.position,
      stableMemory: stableContext(o.memory, p.position),
      volatileMemory: volatileContext(o.memory, p.position, o.context?.volatileTokens, o.context),
      regions: rs,
      image: { w: d.w, h: d.h },
      markedPageDataUrl: withImage ? await markedPageDataUrl(d, rs, undefined, thumb ? THUMB_SIDE : undefined) : undefined,
      crops: withImage && !thumb ? await regionCrops(d, rs, onlyIds ?? cropIds) : [],
      castRefs: await faceReferences(p, o),
      onlyIds,
      preRead,
    });
  }
}
