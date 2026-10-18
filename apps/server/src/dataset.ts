import { readFile } from "node:fs/promises";
import { join } from "node:path";
import type { ReadingPosition } from "@lt/core";
import { env } from "./env";

export interface GtBubble {
  bubble_id: string;
  reading_order: number;
  bbox: { x: number; y: number; w: number; h: number };
  ja_ocr_truth: string;
  vi_gold_trans: string;
}

export interface DatasetPage {
  id: string;
  title: string;
  seriesId: string;
  file: string;
  size: { w: number; h: number };
  position: ReadingPosition;
  gt: GtBubble[];
}

interface RawPage {
  page_id: string;
  source_title: string;
  image_file: string;
  image_size: { w: number; h: number };
  bubbles: GtBubble[];
}

let cache: DatasetPage[] | undefined;

/** Read-only view of the private ground-truth folder. Nothing here is ever written. */
export async function listPages(): Promise<DatasetPage[]> {
  if (cache) return cache;
  if (!env.datasetDir) throw new Error("DATASET_DIR is not set in .env.local");
  const raw = JSON.parse(await readFile(join(env.datasetDir, "ground_truth_benchmark.json"), "utf8")) as RawPage[];
  const counters = new Map<string, number>();
  cache = raw.map((p) => {
    const seriesId = slug(p.source_title);
    const page = (counters.get(seriesId) ?? 0) + 1;
    counters.set(seriesId, page);
    return {
      id: p.page_id,
      title: p.source_title.replace(/\s*\(Manga109\)\s*/i, "").trim(),
      seriesId,
      file: p.image_file,
      size: p.image_size,
      position: { chapter: 1, page },
      gt: p.bubbles,
    };
  });
  return cache;
}

export async function getPage(id: string): Promise<DatasetPage> {
  const page = (await listPages()).find((p) => p.id === id);
  if (!page) throw new Error(`Unknown page ${id}`);
  return page;
}

export async function readPageImage(page: DatasetPage): Promise<Buffer> {
  return readFile(join(env.datasetDir, page.file));
}

const slug = (s: string) =>
  s
    .toLowerCase()
    .replace(/\(manga109\)/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
