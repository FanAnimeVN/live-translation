/**
 * Does a dedicated crop OCR help the cloud reader? The packed page requests (kaggle-pack.ts) are sent to
 * a cloud model three ways: as the product sends them today ("image"), with the crop OCR's reading of
 * each region added ("image+ocr"), and with the OCR text only, no images ("ocr-only"). Replies are
 * written in the Kaggle results layout so kaggle-score.ts scores them the same way.
 *
 *   npx tsx tools/eval/src/hint-cloud.ts [--model anthropic/claude-haiku-5.5] [--ocr baberu] [--variants image,image+ocr,ocr-only]
 */
import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import type { PromptPart } from "@lt/core";
import { PRIVATE_DIR, streamChat } from "@lt/server";

const args = process.argv.slice(2);
const flag = (n: string, d: string) => (args.includes(`--${n}`) ? args[args.indexOf(`--${n}`) + 1] : d);
const model = flag("model", "anthropic/claude-haiku-5.5");
const ocrName = flag("ocr", "baberu");
const variants = flag("variants", "image,image+ocr,ocr-only").split(",");
const pack = join(PRIVATE_DIR, "kaggle", "gt60");
const out = join(PRIVATE_DIR, "kaggle", "cloud-results", "vlm");

const index = JSON.parse(await readFile(join(pack, "index.json"), "utf8")) as { pages: Array<{ pageId: string; split: string }> };
const ocr = JSON.parse(await readFile(join(PRIVATE_DIR, "kaggle", "results", "ocr", `${ocrName}.json`), "utf8")) as { det: Record<string, Record<string, string>> };
const file = (id: string) => `${id.replace(/[^\w.-]/g, "_")}.json`;
let cost = 0;

for (const v of variants) {
  const dir = join(out, `${model.split("/").pop()}-${v}`);
  await mkdir(dir, { recursive: true });
  const done = new Set(await readdir(dir).catch(() => []));
  for (const { pageId } of index.pages.filter((p) => p.split === "test")) {
    if (done.has(file(pageId))) continue;
    const page = JSON.parse(await readFile(join(pack, "pages", file(pageId)), "utf8"));
    let parts: PromptPart[] = page.messages[1].content.map((p: any) => (p.type === "text" ? { type: "text", text: p.text } : { type: "image", dataUrl: p.image_url.url }));
    if (v !== "image") {
      const lines = Object.entries(ocr.det[pageId] ?? {}).filter(([, t]) => t.trim()).map(([id, t]) => `${id}: ${t}`).join("\n");
      parts.push({ type: "text", text: `Pre-read Japanese text of each region by a dedicated OCR model (may contain mistakes; trust the image when they disagree, and keep ja as what is really written):\n${lines}` });
    }
    if (v === "ocr-only") parts = parts.filter((p) => p.type === "text");
    let raw = "";
    try {
      const st = await streamChat({ model, system: page.messages[0].content, parts, purpose: `eval-ocrhint-${v}`, pageId, onText: (d) => (raw += d) });
      cost += st.costUsd;
      await writeFile(join(dir, file(pageId)), JSON.stringify({ model: `${model}-${v}`, pageId, raw, ttfbMs: st.ttfbMs, totalMs: st.totalMs, promptTokens: st.promptTokens, completionTokens: st.completionTokens, costUsd: st.costUsd }));
    } catch (e) {
      console.error(v, pageId, (e as Error).message.slice(0, 160));
    }
  }
  console.log(`${v}: done, spent so far $${cost.toFixed(4)}`);
}
