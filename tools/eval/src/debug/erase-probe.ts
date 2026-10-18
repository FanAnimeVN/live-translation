import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { eraseRegion, sampleBorder, type PageResult } from "@lt/core";
import { decodeImage, getPage, PRIVATE_DIR, readPageImage } from "@lt/server";

const [run, model, pageId, id] = process.argv.slice(2);
const res = JSON.parse(await readFile(join(PRIVATE_DIR, "eval", run, model.replace(/[^a-zA-Z0-9._-]/g, "_"), `${pageId}.json`), "utf8")) as PageResult;
const r = res.regions.find((x) => x.id === id)!;
const d = await decodeImage(await readPageImage(await getPage(pageId)));
const img = d.ctx.getImageData(0, 0, d.w, d.h);
const before = Uint8ClampedArray.from(img.data);
const t = res.translations[id];
const cs = Math.sqrt((r.box.w * r.box.h) / [...t.ja.replace(/\s/g, "")].length);
console.log("region", id, "members", r.members.length, "box", r.box, "bubble", r.bubble, "cs", cs.toFixed(1), "border", sampleBorder(img, r.box));
const rep = eraseRegion(img, r.members, { bubble: r.bubble, mode: r.bubble ? "auto" : "glyph", maxMid: 0.12, charSize: cs });
let changed = 0;
for (let i = 0; i < before.length; i += 4) if (before[i] !== img.data[i]) changed++;
console.log("report", rep, "changed px", changed, "box px", Math.round(r.box.w * r.box.h));
