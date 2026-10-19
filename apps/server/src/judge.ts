/**
 * Blind judging for the team. Every labelled bubble of an eval run (tools/eval/src/bakeoff.ts output)
 * is shown as its source crop with anonymous Vietnamese candidates: each model's translation and the
 * team's gold translation as a hidden control, in a different order for every rater. Scores go to
 * .private/judge/<run>/<rater>.jsonl. Runs only on this machine: page images never leave it.
 */
import { createHash, randomBytes } from "node:crypto";
import { appendFile, mkdir, readdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { Hono } from "hono";
import { createCanvas } from "@napi-rs/canvas";
import { center, clampBox, containment, containsPoint, expand, iou, roundBox, type PageResult, type TextRegion } from "@lt/core";
import { getPage, readPageImage, type DatasetPage } from "./dataset";
import { PRIVATE_DIR, ROOT } from "./env";
import { decodeImage, type DecodedPage } from "./image";

export const judge = new Hono();

const GOLD = "gold (team)";
const safe = (s: string) => s.replace(/[^a-zA-Z0-9._-]/g, "_");
const sha = (s: string) => createHash("sha256").update(s).digest("hex");

interface Candidate { source: string; vi: string }
interface Item { id: string; pageId: string; bubble: string; box: { x: number; y: number; w: number; h: number }; ja: string; candidates: Candidate[] }

/** Same matching rule as the bake-off scoring (tools/eval/src/gt.ts). */
const matches = (g: Item["box"], regions: TextRegion[]) =>
  regions.filter((r) => iou(g, r.box) >= 0.3 || (containsPoint(r.box, center(g)) && containment(g, r.box) >= 0.5) || containment(r.box, g) >= 0.6);

let secret: string | undefined;
async function judgeSecret(): Promise<string> {
  if (secret) return secret;
  const f = join(PRIVATE_DIR, "judge", "secret.txt");
  await mkdir(join(PRIVATE_DIR, "judge"), { recursive: true });
  secret = await readFile(f, "utf8").catch(async () => {
    const s = randomBytes(16).toString("hex");
    await writeFile(f, s, "utf8");
    return s;
  });
  return secret;
}
const cid = async (item: string, source: string) => sha(`${await judgeSecret()}|${item}|${source}`).slice(0, 10);

/** Items per run, rebuilt when the run's model folders change (a model finished translating). */
const items = new Map<string, { sig: string; list: Item[] }>();
async function loadItems(run: string): Promise<Item[]> {
  const base = join(PRIVATE_DIR, "eval", safe(run));
  const listing: Array<{ name: string; files: string[] }> = [];
  for (const d of await readdir(base, { withFileTypes: true })) {
    if (d.isDirectory()) listing.push({ name: d.name, files: (await readdir(join(base, d.name))).filter((f) => f.endsWith(".json")) });
  }
  const sig = listing.map((x) => `${x.name}:${x.files.length}`).join("|");
  const cached = items.get(run);
  if (cached?.sig === sig) return cached.list;
  const models: Array<{ model: string; dir: string; files: Set<string> }> = [];
  for (const { name, files } of listing) {
    if (!files.length) continue;
    const first = JSON.parse(await readFile(join(base, name, files[0]), "utf8")) as PageResult;
    models.push({ model: first.model, dir: join(base, name), files: new Set(files) });
  }
  const shared = [...(models[0]?.files ?? [])].filter((f) => models.every((m) => m.files.has(f))).sort();
  const out: Item[] = [];
  for (const f of shared) {
    const results = await Promise.all(models.map(async (m) => ({ model: m.model, r: JSON.parse(await readFile(join(m.dir, f), "utf8")) as PageResult })));
    const page = await getPage(results[0].r.pageId);
    for (const g of [...page.gt].sort((a, b) => a.reading_order - b.reading_order)) {
      if (!g.vi_gold_trans?.trim() || g.bbox.w <= 0 || g.bbox.h <= 0) continue;
      const candidates: Candidate[] = results.map(({ model, r }) => ({
        source: model,
        vi: matches(g.bbox, r.regions)
          .map((x) => r.translations[x.id])
          .filter(Boolean)
          .sort((a, b) => a!.seq - b!.seq)
          .map((t) => t!.vi)
          .join(" ")
          .trim(),
      }));
      candidates.push({ source: GOLD, vi: g.vi_gold_trans.trim() });
      out.push({ id: `${page.id}|${g.bubble_id}`, pageId: page.id, bubble: g.bubble_id, box: g.bbox, ja: g.ja_ocr_truth, candidates });
    }
  }
  items.set(run, { sig, list: out });
  return out;
}

async function rated(run: string, rater: string): Promise<Array<{ item: string; ratings: Array<{ source: string; meaning: number; natural: number; severe: boolean }>; best?: string }>> {
  const text = await readFile(join(PRIVATE_DIR, "judge", safe(run), `${safe(rater)}.jsonl`), "utf8").catch(() => "");
  return text.split("\n").filter(Boolean).map((l) => JSON.parse(l));
}

judge.get("/judge", async (c) => c.html(await readFile(join(ROOT, "apps", "server", "src", "judge.html"), "utf8")));

/** Items for one rater: candidates anonymous and in the rater's own order; scored items marked. */
judge.get("/api/judge/items", async (c) => {
  const run = c.req.query("run") ?? "team25";
  const rater = (c.req.query("rater") ?? "").trim();
  if (!rater) return c.json({ error: "rater required" }, 400);
  const done = new Set((await rated(run, rater)).map((r) => r.item));
  const list = await loadItems(run);
  const order = (s: string) => sha(`${rater}|${s}`);
  const out = await Promise.all(
    list.map(async (it) => {
      const cands = await Promise.all(it.candidates.map(async (k) => ({ cid: await cid(it.id, k.source), vi: k.vi })));
      return { id: it.id, ja: it.ja, done: done.has(it.id), candidates: cands.sort((a, b) => order(it.id + a.cid).localeCompare(order(it.id + b.cid))) };
    }),
  );
  return c.json({ run, total: out.length, done: done.size, items: out.sort((a, b) => order(a.id).localeCompare(order(b.id))) });
});

const decoded = new Map<string, Promise<DecodedPage>>();
judge.get("/api/judge/crop", async (c) => {
  const run = c.req.query("run") ?? "team25";
  const it = (await loadItems(run)).find((x) => x.id === c.req.query("item"));
  if (!it) return c.notFound();
  let d = decoded.get(it.pageId);
  if (!d) {
    d = getPage(it.pageId).then((p: DatasetPage) => readPageImage(p)).then(decodeImage);
    decoded.set(it.pageId, d);
    if (decoded.size > 12) decoded.delete(decoded.keys().next().value!);
  }
  const page = await d;
  // The balloon with some art around it, so the rater sees who is speaking.
  const b = roundBox(clampBox(expand(it.box, Math.max(40, 0.6 * Math.max(it.box.w, it.box.h))), page.w, page.h));
  const cv = createCanvas(b.w, b.h);
  cv.getContext("2d").drawImage(page.canvas, b.x, b.y, b.w, b.h, 0, 0, b.w, b.h);
  const g = cv.getContext("2d");
  g.strokeStyle = "#e11d48";
  g.lineWidth = 3;
  g.strokeRect(it.box.x - b.x, it.box.y - b.y, it.box.w, it.box.h);
  return new Response(new Uint8Array(await cv.encode("jpeg", 85)), { headers: { "Content-Type": "image/jpeg", "Cache-Control": "no-store" } });
});

judge.post("/api/judge/score", async (c) => {
  const body = await c.req.json<{ run?: string; rater: string; item: string; ratings: Array<{ cid: string; meaning: number; natural: number; severe: boolean }>; best?: string }>();
  const run = body.run ?? "team25";
  const it = (await loadItems(run)).find((x) => x.id === body.item);
  if (!it || !body.rater?.trim()) return c.json({ error: "unknown item or rater" }, 400);
  const byCid = new Map(await Promise.all(it.candidates.map(async (k) => [await cid(it.id, k.source), k.source] as const)));
  const ratings = body.ratings.filter((r) => byCid.has(r.cid)).map((r) => ({ source: byCid.get(r.cid)!, meaning: r.meaning, natural: r.natural, severe: !!r.severe }));
  if (ratings.length !== it.candidates.length) return c.json({ error: "rate every candidate" }, 400);
  await mkdir(join(PRIVATE_DIR, "judge", safe(run)), { recursive: true });
  const line = { at: new Date().toISOString(), rater: body.rater.trim(), item: it.id, ratings, best: body.best ? byCid.get(body.best) : undefined };
  await appendFile(join(PRIVATE_DIR, "judge", safe(run), `${safe(body.rater.trim())}.jsonl`), JSON.stringify(line) + "\n", "utf8");
  return c.json({ ok: true });
});

/** Wilson 95% interval for a share. */
function wilson(k: number, n: number): [number, number] {
  if (!n) return [0, 0];
  const z = 1.96, p = k / n, d = 1 + (z * z) / n;
  const c = (p + (z * z) / (2 * n)) / d, h = (z * Math.sqrt((p * (1 - p)) / n + (z * z) / (4 * n * n))) / d;
  return [Math.max(0, c - h), Math.min(1, c + h)];
}

judge.get("/api/judge/summary", async (c) => {
  const run = c.req.query("run") ?? "team25";
  const dir = join(PRIVATE_DIR, "judge", safe(run));
  const raters = (await readdir(dir).catch(() => [] as string[])).filter((f) => f.endsWith(".jsonl")).map((f) => f.slice(0, -6));
  const per = new Map<string, { n: number; meaning: number; natural: number; severe: number; best: number }>();
  const bestBy = new Map<string, Map<string, string>>();
  let judged = 0;
  for (const r of raters) {
    const rows = await rated(run, r);
    // The latest score of an item counts (a rater may re-score).
    const last = new Map(rows.map((x) => [x.item, x]));
    judged += last.size;
    bestBy.set(r, new Map([...last].filter(([, x]) => x.best).map(([k, x]) => [k, x.best!])));
    for (const x of last.values()) {
      for (const k of x.ratings) {
        const s = per.get(k.source) ?? { n: 0, meaning: 0, natural: 0, severe: 0, best: 0 };
        s.n++;
        s.meaning += k.meaning;
        s.natural += k.natural;
        s.severe += k.severe ? 1 : 0;
        if (x.best === k.source) s.best++;
        per.set(k.source, s);
      }
    }
  }
  // Agreement: share of items two raters both scored where they picked the same best candidate.
  let same = 0, pairs = 0;
  const rs = [...bestBy.values()];
  for (let i = 0; i < rs.length; i++)
    for (let j = i + 1; j < rs.length; j++)
      for (const [item, b] of rs[i]) {
        const o = rs[j].get(item);
        if (!o) continue;
        pairs++;
        if (o === b) same++;
      }
  const total = (await loadItems(run)).length;
  return c.json({
    run,
    items: total,
    raters: raters.length,
    judged,
    agreementOnBest: pairs ? same / pairs : null,
    sources: [...per].map(([source, s]) => ({
      source,
      ratings: s.n,
      meaning: s.meaning / s.n,
      natural: s.natural / s.n,
      severe: s.severe / s.n,
      severeCi: wilson(s.severe, s.n),
      bestShare: s.best / Math.max(1, judged),
    })),
  });
});
