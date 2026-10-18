import { mkdir, readdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import type { PageResult } from "@lt/core";
import { PRIVATE_DIR } from "./env";

/** Text/geometry results only (no images), in .private/. */
const safe = (s: string) => s.replace(/[^a-zA-Z0-9._-]/g, "_");
const dir = (ns: string, model: string) => join(PRIVATE_DIR, "results", safe(ns), safe(model));

export async function saveResult(ns: string, r: PageResult): Promise<void> {
  const d = dir(ns, r.model);
  await mkdir(d, { recursive: true });
  await writeFile(join(d, `${safe(r.pageId)}.json`), JSON.stringify(r), "utf8");
}

export async function loadResult(ns: string, model: string, pageId: string): Promise<PageResult | null> {
  try {
    return JSON.parse(await readFile(join(dir(ns, model), `${safe(pageId)}.json`), "utf8")) as PageResult;
  } catch {
    return null;
  }
}

export async function listResults(ns: string): Promise<Array<{ model: string; pages: string[] }>> {
  const base = join(PRIVATE_DIR, "results", safe(ns));
  try {
    const models = await readdir(base);
    return Promise.all(
      models.map(async (m) => ({ model: m, pages: (await readdir(join(base, m))).map((f) => f.replace(/\.json$/, "")) })),
    );
  } catch {
    return [];
  }
}
