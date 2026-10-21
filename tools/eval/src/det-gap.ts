/**
 * Where does the OCR error grow between label boxes (OCR alone) and detected regions? Splits every label
 * bubble by how the detector covered it, and scores each group on the bake-off's crop OCR output:
 *   clean   one region over this label, and it covers no other label
 *   merged  the region(s) over this label also cover other labels (their text counts against this one)
 *   split   several regions over this label, none shared
 *   missed  no region over this label
 *
 *   npx tsx tools/eval/src/det-gap.ts [--ocr baberu] [--results .private/kaggle/results] [--pack .private/kaggle/gt60]
 */
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { cer, type TextRegion } from "@lt/core";
import { getPage, PRIVATE_DIR } from "@lt/server";
import { matchRegions, validGt } from "./gt";

const args = process.argv.slice(2);
const flag = (n: string, d: string) => (args.includes(`--${n}`) ? args[args.indexOf(`--${n}`) + 1] : d);
const ocr = JSON.parse(await readFile(join(flag("results", join(PRIVATE_DIR, "kaggle", "results")), "ocr", `${flag("ocr", "baberu")}.json`), "utf8")) as { det: Record<string, Record<string, string>> };
const packDir = join(flag("pack", join(PRIVATE_DIR, "kaggle", "gt60")), "pages");

const groups: Record<string, { n: number; edits: number; refLen: number; extra: number }> = {};
const add = (g: string, edits: number, refLen: number, extra = 0) => {
  const x = (groups[g] ??= { n: 0, edits: 0, refLen: 0, extra: 0 });
  x.n++;
  x.edits += edits;
  x.refLen += refLen;
  x.extra += extra;
};
for (const [pageId, byRegion] of Object.entries(ocr.det)) {
  const pack = JSON.parse(await readFile(join(packDir, `${pageId.replace(/[^\w.-]/g, "_")}.json`), "utf8")) as { regions: TextRegion[] };
  const page = await getPage(pageId);
  const size = { w: Math.max(...pack.regions.map((r) => r.box.x + r.box.w)) * 2, h: Math.max(...pack.regions.map((r) => r.box.y + r.box.h)) * 2 };
  const gts = validGt(page.gt, size).filter((g) => g.ja_ocr_truth.trim());
  const owners = new Map<string, number>(); // region id -> labels it covers
  const matches = gts.map((g) => matchRegions(g.bbox, pack.regions));
  for (const m of matches) for (const r of m) owners.set(r.id, (owners.get(r.id) ?? 0) + 1);
  gts.forEach((g, i) => {
    const m = matches[i].sort((a, b) => a.order - b.order);
    const text = m.map((r) => byRegion[r.id] ?? "").join("");
    const c = cer(text, g.ja_ocr_truth);
    const kind = !m.length ? "missed" : m.some((r) => (owners.get(r.id) ?? 0) > 1) ? "merged" : m.length > 1 ? "split" : "clean";
    add(kind, c.edits, c.refLen, Math.max(0, [...text].length - c.refLen));
    add("all", c.edits, c.refLen);
  });
}
console.log("| Detector coverage of a label | Labels | CER | Note |\n|---|---|---|---|");
for (const k of ["clean", "split", "merged", "missed", "all"]) {
  const x = groups[k];
  if (!x) continue;
  const note = k === "merged" ? `~${Math.round(x.extra / Math.max(1, x.n))} extra chars per label from the other bubbles` : "";
  console.log(`| ${k} | ${x.n} | ${((100 * x.edits) / Math.max(1, x.refLen)).toFixed(1)}% | ${note} |`);
}
