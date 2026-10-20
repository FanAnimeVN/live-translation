/**
 * Pronoun agreement with the team's gold Vietnamese (a proxy for the proposal's PCA).
 *
 *   npx tsx tools/eval/src/pronouns.ts <runId>/<model> [<runId>/<model> ...]
 *
 * For every GT bubble with a gold translation, the run's regions over it (same matching as
 * coverage) give the candidate Vietnamese. Personal pronouns and address terms are pulled from
 * both (tôi, tao, tớ, em, anh, chị, cậu, mày, bạn…). On bubbles where the gold uses at least one:
 *   exact  = the candidate uses exactly the same set,
 *   jacc   = mean Jaccard overlap of the two sets,
 *   conflict = both use pronouns but different ones (a real choice of address, not an omission),
 *   "bạn"  = the candidate says "bạn" where the gold does not (the stiff machine default).
 * It is a proxy: kinship words are also ordinary nouns ("chị gái tôi"), and the gold is one team's
 * choice. Use it to compare runs on the same pages, not as an absolute score.
 * Also: on every dialogue/thought region of the run, how often the speaker and the listener are a
 * name, a label for someone not yet named ("(girl, short hair)") or "unknown".
 */
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { isNamed, type PageResult } from "@lt/core";
import { listPages, PRIVATE_DIR } from "@lt/server";
import { matchRegions, validGt } from "./gt";

const PRONOUNS = new Set([
  "tôi", "tao", "tớ", "mình", "ta", "tui", "em", "anh", "chị", "cô", "cậu", "mày", "bạn", "ông", "bà", "chú", "bác",
  "cháu", "con", "ngài", "nhóc", "nó", "họ", "chúng", "bọn", "ổng", "bả", "thím", "dì", "mợ", "cưng",
]);
const safe = (s: string) => s.replace(/[^a-zA-Z0-9._-]/g, "_");
const words = (s: string) => (s.toLowerCase().normalize("NFC").match(/\p{L}+/gu) ?? []).filter((w) => PRONOUNS.has(w));

const pages = await listPages();
for (const spec of process.argv.slice(2)) {
  const run = spec.slice(0, spec.indexOf("/"));
  const model = spec.slice(spec.indexOf("/") + 1);
  let bubbles = 0, withGold = 0, exact = 0, jacc = 0, ban = 0, missing = 0, conflict = 0, omitted = 0;
  const who = { lines: 0, speaker: { named: 0, label: 0 }, to: { named: 0, label: 0 } };
  for (const page of pages) {
    let res: PageResult;
    try {
      res = JSON.parse(await readFile(join(PRIVATE_DIR, "eval", run, safe(model), `${safe(page.id)}.json`), "utf8"));
    } catch {
      continue;
    }
    for (const t of Object.values(res.translations)) {
      if (t.role !== "dialogue" && t.role !== "thought") continue;
      who.lines++;
      for (const k of ["speaker", "to"] as const) {
        if (isNamed(t[k])) who[k].named++;
        else if (t[k] && t[k] !== "unknown") who[k].label++;
      }
    }
    for (const g of validGt(page.gt, page.size)) {
      if (!g.vi_gold_trans?.trim()) continue;
      bubbles++;
      const gold = new Set(words(g.vi_gold_trans));
      if (!gold.size) continue;
      withGold++;
      const ts = res.translations;
      const matched = matchRegions(g.bbox, res.regions).filter((r) => ts[r.id]?.vi).sort((a, b) => ts[a.id].seq - ts[b.id].seq);
      if (!matched.length) {
        missing++;
        continue;
      }
      const cand = new Set(words(matched.map((r) => ts[r.id].vi).join(" ")));
      const inter = [...gold].filter((w) => cand.has(w)).length;
      const uni = new Set([...gold, ...cand]).size;
      if (inter === gold.size && cand.size === gold.size) exact++;
      else if (!cand.size) omitted++;
      else conflict++;
      jacc += uni ? inter / uni : 1;
      if (cand.has("bạn") && !gold.has("bạn")) ban++;
    }
  }
  const pct = (n: number) => `${((100 * n) / Math.max(1, withGold)).toFixed(1)}%`;
  const share = (n: number) => `${((100 * n) / Math.max(1, who.lines)).toFixed(0)}%`;
  const unknown = (k: "speaker" | "to") => who.lines - who[k].named - who[k].label;
  console.log(
    `${spec.padEnd(55)} gold bubbles ${bubbles}, with pronouns ${withGold} | exact ${pct(exact)} | jaccard ${(jacc / Math.max(1, withGold - missing)).toFixed(3)} | omitted ${pct(omitted)} | conflict ${pct(conflict)} | "bạn" not in gold ${pct(ban)} | not translated ${missing}\n` +
      `${"".padEnd(55)} ${who.lines} dialogue/thought lines: speaker named ${share(who.speaker.named)}, label ${share(who.speaker.label)}, unknown ${share(unknown("speaker"))} | listener named ${share(who.to.named)}, label ${share(who.to.label)}, unknown ${share(unknown("to"))}`,
  );
}
