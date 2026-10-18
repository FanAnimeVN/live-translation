import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { emptyMemory, type SeriesMemory } from "@lt/core";
import { PRIVATE_DIR } from "./env";

/** Story memory lives in .private/ (gitignored): it is the reader's data, never committed. */
const file = (ns: string, seriesId: string) => join(PRIVATE_DIR, "memory", safe(ns), `${safe(seriesId)}.json`);
const safe = (s: string) => s.replace(/[^a-zA-Z0-9._-]/g, "_");

export async function loadMemory(ns: string, seriesId: string, title: string): Promise<SeriesMemory> {
  try {
    return JSON.parse(await readFile(file(ns, seriesId), "utf8")) as SeriesMemory;
  } catch {
    return emptyMemory(seriesId, title);
  }
}

export async function saveMemory(ns: string, mem: SeriesMemory): Promise<void> {
  const f = file(ns, mem.seriesId);
  await mkdir(join(f, ".."), { recursive: true });
  await writeFile(f, JSON.stringify(mem, null, 1), "utf8");
}
