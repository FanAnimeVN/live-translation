/**
 * How many labelled bubbles does the detector miss or merge, with and without the second detector (CTD)?
 * Detection only (no OCR, no API). Run once per setting:
 *
 *   DETECT_CTD=0 npx tsx tools/eval/src/det-coverage.ts
 *   DETECT_CTD=1 npx tsx tools/eval/src/det-coverage.ts
 */
import { decodeImage, detect, listPages, readPageImage } from "@lt/server";
import { matchRegions, validGt } from "./gt";

let labels = 0, missed = 0, merged = 0, regions = 0, ms = 0;
for (const page of (await listPages()).filter((p) => p.gt.length)) {
  const d = await decodeImage(await readPageImage(page));
  const t = performance.now();
  const det = await detect(d);
  ms += performance.now() - t;
  regions += det.regions.length;
  const gts = validGt(page.gt, d).filter((g) => g.ja_ocr_truth.trim());
  const owners = new Map<string, number>();
  const matches = gts.map((g) => matchRegions(g.bbox, det.regions));
  for (const m of matches) for (const r of m) owners.set(r.id, (owners.get(r.id) ?? 0) + 1);
  for (const m of matches) {
    labels++;
    if (!m.length) missed++;
    else if (m.some((r) => (owners.get(r.id) ?? 0) > 1)) merged++;
  }
}
console.log(`DETECT_CTD=${process.env.DETECT_CTD ?? "default"}: ${labels} labels, missed ${missed} (${((100 * missed) / labels).toFixed(1)}%), merged ${merged} (${((100 * merged) / labels).toFixed(1)}%), ${regions} regions, ${(ms / 1000).toFixed(1)} s detection`);
