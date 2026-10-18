/**
 * Detector-only check on the private GT pages: recall of GT text boxes and region
 * counts. No network, no cost. Usage: npm run detect [-- --min-score 0.3]
 */
import { decodeImage, detect, listPages, readPageImage } from "@lt/server";
import { matchRegions, validGt } from "./gt";

const arg = (name: string, def: string) => {
  const i = process.argv.indexOf(`--${name}`);
  return i > 0 ? process.argv[i + 1] : def;
};
const minScore = Number(arg("min-score", "0.3"));

const pages = await listPages();
let found = 0;
let total = 0;
const times: number[] = [];
for (const page of pages) {
  const decoded = await decodeImage(await readPageImage(page));
  const det = await detect(decoded, minScore);
  times.push(det.ms);
  const gt = validGt(page.gt, { w: decoded.w, h: decoded.h });
  const missed = gt.filter((g) => matchRegions(g.bbox, det.regions).length === 0);
  found += gt.length - missed.length;
  total += gt.length;
  const cls = det.detections.reduce<Record<string, number>>((m, d) => ((m[d.cls] = (m[d.cls] ?? 0) + 1), m), {});
  console.log(
    `${page.id.padEnd(9)} ${decoded.w}x${decoded.h} gt=${String(gt.length).padStart(2)} found=${String(gt.length - missed.length).padStart(2)} ` +
      `regions=${String(det.regions.length).padStart(2)} raw=${JSON.stringify(cls)} ${Math.round(det.ms)}ms` +
      (missed.length ? ` missed=${missed.map((m) => m.bubble_id).join(",")}` : "") +
      (gt.length !== page.gt.length ? ` (excluded ${page.gt.length - gt.length} invalid GT boxes)` : ""),
  );
}
console.log(`\nRecall ${found}/${total} = ${((100 * found) / total).toFixed(1)}%  (minScore ${minScore})`);
console.log(`Detector ms: first(cold)=${Math.round(times[0])} warm median=${Math.round(times.slice(1).sort((a, b) => a - b)[Math.floor((times.length - 1) / 2)])}`);
