/**
 * Check the server's crop OCR (apps/server/src/ocr.ts, Baberu ONNX on this machine's CPU) on the team's
 * test pages: CER on the label boxes (OCR alone) and on the detected regions (as the pipeline reads them),
 * plus ms per crop. Compare with the bake-off numbers of the same model in PyTorch (docs/LOCAL-MODELS.md).
 *
 *   npx tsx tools/eval/src/ocr-local.ts [--pages @.cache/tmp/team25-pages.txt] [--max 25]
 */
import { readFile } from "node:fs/promises";
import { cer } from "@lt/core";
import { decodeImage, detect, getPage, readPageImage } from "@lt/server";
import { loadOcr, readBox, readRegions } from "../../../apps/server/src/ocr";
import { matchRegions, validGt } from "./gt";

const args = process.argv.slice(2);
const flag = (n: string, d: string) => (args.includes(`--${n}`) ? args[args.indexOf(`--${n}`) + 1] : d);
const list = flag("pages", "@.cache/tmp/team25-pages.txt");
const ids = (list.startsWith("@") ? await readFile(list.slice(1), "utf8") : list).split(/[,\s]+/).filter(Boolean).slice(0, Number(flag("max", "25")));

const t0 = performance.now();
await loadOcr();
console.log(`OCR loaded in ${Math.round(performance.now() - t0)} ms`);
let e1 = 0, l1 = 0, exact = 0, n1 = 0, e2 = 0, l2 = 0, crops = 0, ms = 0;
const pageMs: number[] = [];
for (const id of ids) {
  const page = await getPage(id);
  const d = await decodeImage(await readPageImage(page));
  const gt = validGt(page.gt, d).filter((g) => g.ja_ocr_truth.trim());
  for (const g of gt) {
    const t = performance.now();
    const c = cer(await readBox(d, g.bbox), g.ja_ocr_truth);
    ms += performance.now() - t;
    crops++;
    e1 += c.edits;
    l1 += c.refLen;
    n1++;
    if (!c.edits) exact++;
  }
  const det = await detect(d);
  const t = performance.now();
  const read = await readRegions(d, det.regions); // as the pipeline reads a page: crops decoded in parallel
  pageMs.push(performance.now() - t);
  for (const g of gt) {
    const matched = matchRegions(g.bbox, det.regions).sort((a, b) => a.order - b.order);
    const c = cer(matched.map((r) => read[r.id]).join(""), g.ja_ocr_truth);
    e2 += c.edits;
    l2 += c.refLen;
  }
  console.log(`${id}: ${gt.length} labels, ${det.regions.length} regions`);
}
console.log(`\nLabel boxes: CER ${((100 * e1) / l1).toFixed(1)}%, exact ${((100 * exact) / n1).toFixed(0)}% (${n1} lines)`);
console.log(`Detected regions: CER ${((100 * e2) / l2).toFixed(1)}%`);
console.log(`Speed: ${(ms / crops).toFixed(0)} ms per label crop one at a time; a page of detected regions (parallel) p50 ${[...pageMs].sort((a, b) => a - b)[Math.floor(pageMs.length / 2)].toFixed(0)} ms, max ${Math.max(...pageMs).toFixed(0)} ms`);
