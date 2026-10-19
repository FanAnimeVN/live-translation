import { writeFile } from "node:fs/promises";
import { join } from "node:path";
import {
  applyRegionRules,
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
  type PageNotes,
  type PageResult,
  type ReadingPosition,
  type RegionTranslation,
  type SeriesMemory,
  type TextRegion,
  type TranslateEvent,
} from "@lt/core";
import { detect, detectInCrop } from "./detector";
import { decodeImage, markedPageDataUrl, regionCrops, type DecodedPage } from "./image";
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

  const translations: Record<string, RegionTranslation> = {};
  const notes: PageNotes = { names: [], address: [], missed: [] };
  const usage = { promptTokens: 0, completionTokens: 0, cachedTokens: 0, costUsd: 0 };
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
      system: SYSTEM_PROMPT,
      parts: await requestParts(page, decoded, regions, opts, onlyIds),
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

  const result: PageResult = {
    pageId: page.id,
    seriesId: page.seriesId,
    position: page.position,
    image: { w: decoded.w, h: decoded.h },
    regions: [...regions, ...placed.map((p) => p.region)],
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

  async function placeMissed(d: DecodedPage, rs: TextRegion[], missed: MissedNote[]): Promise<Array<{ region: TextRegion; note: MissedNote }>> {
    const out: Array<{ region: TextRegion; note: MissedNote }> = [];
    const taken = rs.map((r) => r.bubble ?? r.box);
    for (const note of missed) {
      if (!note.box || !note.vi || note.role === "sfx" || note.role === "decorative" || note.role === "none") continue;
      const rough = fromPermille(note.box, d.w, d.h);
      const size = Math.max(rough.w, rough.h);
      const search = roundBox(clampBox(expand(rough, Math.max(16, size * 0.6)), d.w, d.h));
      const near = expand(rough, size * 0.5);
      const best = (await detectInCrop(d, search, 0.2))
        .filter((c) => iou(c.box, rough) > 0.05 || containsPoint(near, center(c.box)))
        .filter((c) => !taken.some((t) => containment(c.box, t) > 0.5 || containment(t, c.box) > 0.5))
        .sort((a, b) => iou(b.box, rough) - iou(a.box, rough) || b.score - a.score)[0];
      if (!best) continue;
      taken.push(best.box);
      const k = out.length + 1;
      out.push({ region: { id: `m${k}`, kind: "free", box: best.box, members: [best.box], score: Math.round(best.score * 1000) / 1000, order: rs.length + k - 1 }, note });
    }
    return out;
  }

  async function requestParts(p: PageInput, d: DecodedPage, rs: TextRegion[], o: TranslateOptions, onlyIds?: string[]) {
    const cropIds = o.crops === "all" ? rs.map((r) => r.id) : o.crops === "none" ? [] : undefined;
    return buildUserParts({
      title: p.title,
      position: p.position,
      stableMemory: stableContext(o.memory, p.position),
      volatileMemory: volatileContext(o.memory, p.position),
      regions: rs,
      image: { w: d.w, h: d.h },
      markedPageDataUrl: await markedPageDataUrl(d, rs),
      crops: await regionCrops(d, rs, onlyIds ?? cropIds),
      onlyIds,
    });
  }
}
