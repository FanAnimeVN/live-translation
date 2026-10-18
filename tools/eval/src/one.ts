/**
 * Translate one GT page and print streamed regions with timings.
 * Usage: npx tsx tools/eval/src/one.ts MN109-02 [model]
 */
import { emptyMemory } from "@lt/core";
import { DEFAULT_MODEL, getPage, readPageImage, spentUsd, translatePage } from "@lt/server";

const pageId = process.argv[2] ?? "MN109-02";
const model = process.argv[3] ?? DEFAULT_MODEL;
const page = await getPage(pageId);
const result = await translatePage(
  { id: page.id, title: page.title, seriesId: page.seriesId, position: page.position, bytes: await readPageImage(page) },
  {
    model,
    memory: emptyMemory(page.seriesId, page.title),
    emit: (e) => {
      if (e.type === "detected") console.log(`detected ${e.regions.length} regions in ${Math.round(e.detectMs)} ms`);
      if (e.type === "region")
        console.log(`${String(e.atMs).padStart(6)}ms ${e.t.id.padEnd(4)} [${e.t.role}] ${e.t.speaker}→${e.t.to} | ${e.t.ja} => ${e.t.vi}${e.t.fixes.length ? ` (fix: ${e.t.fixes})` : ""}`);
      if (e.type === "notes") console.log("notes", JSON.stringify(e.notes));
    },
  },
);
console.log("\ntimings", result.timings, "usage", result.usage, "missing", result.missingIds, "repaired", result.repairedIds);
console.log("ledger spent so far $", (await spentUsd()).toFixed(5));
