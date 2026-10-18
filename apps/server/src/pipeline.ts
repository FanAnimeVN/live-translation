import {
  buildUserParts,
  isNotesObject,
  JsonObjectStream,
  memoryContext,
  parseNotesObject,
  parseRegionObject,
  PROMPT_VERSION,
  SYSTEM_PROMPT,
  type PageNotes,
  type PageResult,
  type ReadingPosition,
  type RegionTranslation,
  type SeriesMemory,
  type TextRegion,
  type TranslateEvent,
} from "@lt/core";
import { detect } from "./detector";
import { decodeImage, markedPageDataUrl, regionCrops, type DecodedPage } from "./image";
import { mockReply } from "./mock";
import { streamChat } from "./openrouter";

export interface PageInput {
  id: string;
  title: string;
  seriesId: string;
  position: ReadingPosition;
  bytes: Buffer;
}

export interface TranslateOptions {
  model: string;
  memory: SeriesMemory;
  emit?: (e: TranslateEvent) => void;
  signal?: AbortSignal;
  /** Attach zoomed crops: "small" regions only (default), "all" or "none". */
  crops?: "small" | "all" | "none";
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

  const translations: Record<string, RegionTranslation> = {};
  const notes: PageNotes = { names: [], address: [], missed: [] };
  const usage = { promptTokens: 0, completionTokens: 0, costUsd: 0 };
  let firstRegionMs: number | undefined;
  let ttfbMs: number | undefined;
  let seq = 0;

  const run = async (onlyIds?: string[]) => {
    const ids = new Set((onlyIds ?? regions.map((r) => r.id)).filter((id) => !translations[id]));
    const parser = new JsonObjectStream((value) => {
      if (isNotesObject(value)) {
        const n = parseNotesObject(value);
        if (n) {
          notes.names.push(...n.names);
          notes.address.push(...n.address);
          notes.missed.push(...n.missed);
          emit({ type: "notes", notes: n });
        }
        return;
      }
      const t = parseRegionObject(value, ids, seq);
      if (!t || translations[t.id]) return;
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
    const stats = await streamChat({
      model: opts.model,
      system: SYSTEM_PROMPT,
      parts: await requestParts(page, decoded, regions, opts, onlyIds),
      purpose: onlyIds ? "repair" : "translate-page",
      pageId: page.id,
      signal: opts.signal,
      onText: (d) => parser.push(d),
    });
    ttfbMs ??= stats.ttfbMs;
    usage.promptTokens += stats.promptTokens ?? 0;
    usage.completionTokens += stats.completionTokens ?? 0;
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

  const result: PageResult = {
    pageId: page.id,
    seriesId: page.seriesId,
    position: page.position,
    image: { w: decoded.w, h: decoded.h },
    regions,
    translations,
    notes,
    model: opts.model,
    promptVersion: PROMPT_VERSION,
    timings: {
      detectMs: Math.round(det.ms),
      ttfbMs: ttfbMs === undefined ? undefined : Math.round(ttfbMs),
      firstRegionMs: firstRegionMs === undefined ? undefined : Math.round(firstRegionMs),
      totalMs: Math.round(performance.now() - t0),
    },
    usage,
    missingIds: missing,
    repairedIds,
    createdAt: new Date().toISOString(),
  };
  emit({ type: "done", result });
  return result;

  async function requestParts(p: PageInput, d: DecodedPage, rs: TextRegion[], o: TranslateOptions, onlyIds?: string[]) {
    const cropIds = o.crops === "all" ? rs.map((r) => r.id) : o.crops === "none" ? [] : undefined;
    return buildUserParts({
      title: p.title,
      position: p.position,
      memory: memoryContext(o.memory, p.position),
      regions: rs,
      image: { w: d.w, h: d.h },
      markedPageDataUrl: await markedPageDataUrl(d, rs),
      crops: await regionCrops(d, rs, onlyIds ?? cropIds),
      onlyIds,
    });
  }
}
