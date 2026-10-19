/**
 * First-bubble latency of the page request under different model routings, replaying the packed
 * page requests (tools/eval/src/kaggle-pack.ts) straight to OpenRouter: time to the first token,
 * to the first complete region object (the first bubble a reader sees), and to the end, plus
 * cost. Routings are interleaved page by page so network and time-of-day hit them alike.
 * Every call goes to the cost ledger.
 *
 *   npx tsx tools/eval/src/latency.ts [--pages 10] [--configs haiku,haiku-anthropic,haiku-race,deepseek]
 */
import { readFile, readdir } from "node:fs/promises";
import { join } from "node:path";
import { percentile } from "@lt/core";
import { env, PRIVATE_DIR } from "@lt/server";
import { record } from "../../../apps/server/src/ledger";

const args = process.argv.slice(2);
const flag = (n: string, d: string) => (args.includes(`--${n}`) ? args[args.indexOf(`--${n}`) + 1] : d);
const nPages = Number(flag("pages", "10"));
const configs = flag("configs", "haiku,haiku-anthropic,haiku-race,deepseek").split(",");
const PRICE: Record<string, [number, number]> = { "anthropic/claude-haiku-5.5": [0.1, 0.5], "deepseek/deepseek-v4.1-flash-1017": [0.08, 0.5] };

interface Route { model: string; provider: Record<string, unknown>; extra: Record<string, unknown>; cache: boolean }
const HAIKU = "anthropic/claude-haiku-5.5";
const haiku = (provider: Record<string, unknown>): Route => ({ model: HAIKU, provider: { data_collection: "deny", ...provider }, extra: { reasoning: { enabled: false } }, cache: true });
const ROUTES: Record<string, Route[]> = {
  haiku: [haiku({ sort: "latency" })],
  "haiku-anthropic": [haiku({ order: ["Anthropic"], allow_fallbacks: false })],
  // Two providers at once: the first to stream wins, the other is cancelled.
  "haiku-race": [haiku({ order: ["Anthropic"], allow_fallbacks: false }), haiku({ sort: "latency", ignore: ["Anthropic"] })],
  deepseek: [
    {
      model: "deepseek/deepseek-v4.1-flash-1017",
      provider: { data_collection: "deny", order: ["InferenceNet", "DeepInfra"], allow_fallbacks: true, ignore: ["Relace", "Morph"] },
      extra: { reasoning: { enabled: false }, temperature: 0.2 },
      cache: false,
    },
  ],
};

interface Timing { ttfb?: number; first?: number; total: number; cost: number; provider?: string; error?: string }

/** One streamed request; `onFirst` fires with the first text delta. */
async function stream(route: Route, messages: any[], signal: AbortSignal, onFirst: () => void): Promise<Timing> {
  const msgs = route.cache ? [{ role: "system", content: [{ type: "text", text: messages[0].content, cache_control: { type: "ephemeral" } }] }, messages[1]] : messages;
  const t0 = performance.now();
  const out: Timing = { total: 0, cost: 0 };
  let text = "";
  let usage: any;
  try {
    const res = await fetch("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST",
      signal,
      headers: { Authorization: `Bearer ${env.openrouterKey}`, "Content-Type": "application/json", "X-Title": "Live translation (dev)" },
      body: JSON.stringify({ model: route.model, stream: true, max_tokens: 6000, usage: { include: true }, provider: route.provider, ...route.extra, messages: msgs }),
    });
    if (!res.ok || !res.body) throw new Error(`${res.status} ${(await res.text()).slice(0, 200)}`);
    const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
    let buf = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += value;
      let nl: number;
      while ((nl = buf.indexOf("\n")) >= 0) {
        const line = buf.slice(0, nl).trim();
        buf = buf.slice(nl + 1);
        if (!line.startsWith("data:") || line.endsWith("[DONE]")) continue;
        let chunk: any;
        try {
          chunk = JSON.parse(line.slice(5));
        } catch {
          continue;
        }
        out.provider ??= chunk.provider;
        const delta = chunk.choices?.[0]?.delta?.content;
        if (typeof delta === "string" && delta) {
          if (out.ttfb === undefined) {
            out.ttfb = performance.now() - t0;
            onFirst();
          }
          text += delta;
          // The first bubble: the first complete object carrying a translation.
          if (out.first === undefined && /"vi"\s*:\s*"(?:[^"\\]|\\.)*"[^{}]*\}/.test(text)) out.first = performance.now() - t0;
        }
        if (chunk.usage) usage = chunk.usage;
      }
    }
  } catch (e) {
    out.error = (e as Error).name === "AbortError" ? "cancelled" : (e as Error).message;
  }
  out.total = performance.now() - t0;
  const [inUsd, outUsd] = PRICE[route.model];
  // A cancelled racer has no usage report: charge its whole prompt, conservatively.
  out.cost = usage ? Number(usage.cost ?? 0) : out.error === "cancelled" ? (5500 * inUsd) / 1e6 : 0;
  await record({ at: new Date().toISOString(), model: route.model, purpose: "eval-latency", ok: !out.error, costUsd: out.cost, promptTokens: usage?.prompt_tokens, completionTokens: usage?.completion_tokens, cachedTokens: usage?.prompt_tokens_details?.cached_tokens, ms: Math.round(out.total), ttfbMs: out.ttfb && Math.round(out.ttfb), provider: out.provider, error: out.error });
  return out;
}

async function run(name: string, messages: any[]): Promise<Timing> {
  const routes = ROUTES[name];
  if (routes.length === 1) return stream(routes[0], messages, new AbortController().signal, () => {});
  const ctrls = routes.map(() => new AbortController());
  let winner = -1;
  const results = await Promise.all(
    routes.map((r, i) =>
      stream(r, messages, ctrls[i].signal, () => {
        if (winner >= 0) return;
        winner = i;
        ctrls.forEach((c, j) => j !== i && c.abort());
      }),
    ),
  );
  const w = results[winner >= 0 ? winner : 0];
  return { ...w, cost: results.reduce((a, r) => a + r.cost, 0), provider: `${w.provider} (won ${winner})` };
}

const packDir = join(PRIVATE_DIR, "kaggle", "pack", "pages");
const files = (await readdir(packDir)).filter((f) => f.endsWith(".json")).sort().slice(0, nPages);
const all: Record<string, Timing[]> = Object.fromEntries(configs.map((c) => [c, []]));
for (const f of files) {
  const req = JSON.parse(await readFile(join(packDir, f), "utf8"));
  for (const c of configs) {
    const t = await run(c, req.messages);
    all[c].push(t);
    console.log(`${req.pageId.padEnd(32)} ${c.padEnd(16)} ttfb ${Math.round(t.ttfb ?? -1)} first ${Math.round(t.first ?? -1)} total ${Math.round(t.total)} $${t.cost.toFixed(5)} ${t.provider ?? ""} ${t.error ?? ""}`);
  }
}
const s = (v: number[], p: number) => (v.length ? (percentile(v, p / 100) / 1000).toFixed(1) + " s" : "—");
console.log("\n| Routing | Pages | First token p50 | p90 | First bubble p50 | p90 | Page p50 | $/page |\n|---|---|---|---|---|---|---|---|");
for (const c of configs) {
  const ts = all[c].filter((t) => !t.error || t.error === "cancelled");
  const ttfb = ts.map((t) => t.ttfb!).filter((x) => x !== undefined);
  const first = ts.map((t) => t.first!).filter((x) => x !== undefined);
  console.log(`| ${c} | ${ts.length} | ${s(ttfb, 50)} | ${s(ttfb, 90)} | ${s(first, 50)} | ${s(first, 90)} | ${s(ts.map((t) => t.total), 50)} | $${(ts.reduce((a, t) => a + t.cost, 0) / Math.max(1, ts.length)).toFixed(5)} |`);
}
