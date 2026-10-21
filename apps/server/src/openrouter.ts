import type { PromptPart } from "@lt/core";
import { assertLocalUrl, env } from "./env";
import { assertBudget, record } from "./ledger";
import { estimateUsd, modelInfo } from "./models";

export interface StreamStats {
  ttfbMs?: number;
  totalMs: number;
  promptTokens?: number;
  completionTokens?: number;
  cachedTokens?: number;
  cacheWriteTokens?: number;
  costUsd: number;
  finishReason?: string;
  provider?: string;
  retries?: number;
}

export class ProviderError extends Error {
  constructor(message: string, readonly status?: number, readonly code = "provider") {
    super(message);
  }
}

/**
 * Stream a chat completion from OpenRouter, calling `onText` with each text delta.
 * Every attempt (ok or failed) is written to the cost ledger.
 */
export async function streamChat(opts: {
  model: string;
  system: string;
  parts: PromptPart[];
  purpose: string;
  pageId?: string;
  maxTokens?: number;
  signal?: AbortSignal;
  /** Provider routing: reading waits on the fastest provider, background work takes the cheapest. */
  sort?: "latency" | "price";
  /** Request fields applied after the model's defaults (e.g. reasoning off for background work). */
  extra?: Record<string, unknown>;
  onText: (delta: string) => void;
}): Promise<StreamStats> {
  // "local/<name>": a model served on this machine (Ollama, LM Studio). No key, no credits,
  // and never a request to another host.
  const local = opts.model.startsWith("local/");
  // "ollama-cloud/<tag>": Ollama's hosted models through the signed-in local daemon. A cloud
  // service (pages leave the machine), measured like the others; never part of offline mode.
  const ollamaCloud = opts.model.startsWith("ollama-cloud/");
  // Ollama ":cloud" tags answer through the local daemon but run on Ollama's servers: never offline.
  if (local && /[:-]cloud$/.test(opts.model))
    throw new ProviderError(`${opts.model} runs on Ollama's cloud, not on this machine: offline mode never sends pages to another host`, 400, "not-local");
  if (!local && !ollamaCloud && !env.openrouterKey) throw new ProviderError("OPENROUTER_API_KEY is missing in .env.local", 401, "no-key");
  if (!local && !ollamaCloud) await assertBudget(estimateUsd(opts.model));
  const info = modelInfo(opts.model);
  // Local Ollama (its default port): native chat API, the only one that can raise the context size.
  const ollamaNative = local && new URL(env.localLlmUrl).port === "11434";
  // Explicit cache breakpoints for providers that need them (Anthropic, Gemini);
  // DeepSeek, GLM and Qwen cache identical prefixes automatically.
  const explicitCache = /^(anthropic|google)\//.test(opts.model);
  const cacheMark = explicitCache ? { cache_control: { type: "ephemeral" } } : {};
  const body = ollamaNative
    ? {
        model: opts.model.slice("local/".length),
        stream: true,
        options: { temperature: 0.2, num_ctx: env.localNumCtx, num_predict: opts.maxTokens ?? 6000 },
        // Content parts become consecutive messages in order, as Ollama's OpenAI endpoint does itself.
        messages: [
          ...(opts.system ? [{ role: "system", content: opts.system }] : []),
          ...opts.parts.map((p) => (p.type === "text" ? { role: "user", content: p.text } : { role: "user", content: "", images: [p.dataUrl.slice(p.dataUrl.indexOf(",") + 1)] })),
        ],
      }
    : local || ollamaCloud
    ? {
        model: (info.apiId ?? opts.model).slice(opts.model.indexOf("/") + 1),
        stream: true,
        stream_options: { include_usage: true },
        max_tokens: opts.maxTokens ?? 6000,
        temperature: 0.2,
        // Model fields (reasoning effort, a larger cap for thinking models) after the defaults.
        ...(ollamaCloud ? info.extra : {}),
        messages: [
          // Translation-only models (Hy-MT2) take their instruction in the user turn, no system prompt.
          ...(opts.system ? [{ role: "system", content: opts.system }] : []),
          { role: "user", content: opts.parts.map((p) => (p.type === "text" ? { type: "text", text: p.text } : { type: "image_url", image_url: { url: p.dataUrl } })) },
        ],
      }
    : {
        model: info.apiId ?? opts.model,
        stream: true,
        max_tokens: opts.maxTokens ?? 6000,
        ...(info.noSampling ? {} : { temperature: 0.2 }),
        usage: { include: true },
        // Background work (text only) takes the cheapest provider; interactive reading follows the
        // model's measured provider preferences, else the fastest.
        provider: opts.sort === "price" ? { data_collection: "deny", sort: "price" } : { data_collection: "deny", ...(info.provider ?? { sort: opts.sort ?? "latency" }) },
        ...info.extra,
        ...opts.extra,
        messages: [
          { role: "system", content: explicitCache ? [{ type: "text", text: opts.system, ...cacheMark }] : opts.system },
          {
            role: "user",
            content: opts.parts.map((p) =>
              p.type === "text"
                ? { type: "text", text: p.text, ...(p.cache ? cacheMark : {}) }
                : { type: "image_url", image_url: { url: p.dataUrl } },
            ),
          },
        ],
      };

  const payload = JSON.stringify(body);
  const t0 = performance.now();
  const stats: StreamStats = { totalMs: 0, costUsd: 0 };
  let ok = false;
  let error: string | undefined;
  try {
    let res: Response;
    for (let attempt = 0; ; attempt++) {
      try {
        res = local || ollamaCloud
          ? await fetch(ollamaNative ? new URL("/api/chat", assertLocalUrl(env.localLlmUrl)) : new URL("chat/completions", assertLocalUrl(env.localLlmUrl.replace(/\/?$/, "/"))), {
              method: "POST",
              signal: opts.signal,
              headers: { "Content-Type": "application/json" },
              body: payload,
            })
          : await fetch("https://openrouter.ai/api/v1/chat/completions", {
              method: "POST",
              signal: opts.signal,
              headers: {
                Authorization: `Bearer ${env.openrouterKey}`,
                "Content-Type": "application/json",
                "X-Title": "Live translation (dev)",
              },
              body: payload,
            });
        break;
      } catch (e) {
        // The connection failed before any response (e.g. ECONNRESET): nothing streamed, retry once.
        if (attempt >= 1 || opts.signal?.aborted) throw e;
        stats.retries = attempt + 1;
        await new Promise((r) => setTimeout(r, 800));
      }
    }
    if (!res.ok || !res.body) {
      const text = await res.text().catch(() => "");
      throw new ProviderError(`${local ? "Local model server" : ollamaCloud ? "Ollama cloud" : "OpenRouter"} ${res.status}: ${text.slice(0, 400)}`, res.status, statusCode(res.status));
    }
    const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
    let buf = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      stats.ttfbMs ??= performance.now() - t0;
      buf += value;
      let nl: number;
      while ((nl = buf.indexOf("\n")) >= 0) {
        const line = buf.slice(0, nl).trim();
        buf = buf.slice(nl + 1);
        if (ollamaNative) {
          // Native Ollama stream: one JSON object per line.
          if (!line) continue;
          let c: any;
          try {
            c = JSON.parse(line);
          } catch {
            continue;
          }
          if (c.error) throw new ProviderError(`Local model server: ${c.error}`, 400, "provider");
          const delta = c.message?.content;
          if (typeof delta === "string" && delta) opts.onText(delta);
          if (c.done) {
            stats.finishReason = c.done_reason;
            stats.promptTokens = c.prompt_eval_count;
            stats.completionTokens = c.eval_count;
          }
          continue;
        }
        if (!line.startsWith("data:")) continue;
        const data = line.slice(5).trim();
        if (data === "[DONE]") continue;
        let chunk: any;
        try {
          chunk = JSON.parse(data);
        } catch {
          continue;
        }
        if (chunk.error) throw new ProviderError(`Model error: ${chunk.error.message ?? JSON.stringify(chunk.error)}`, chunk.error.code);
        stats.provider ??= chunk.provider;
        const choice = chunk.choices?.[0];
        const delta = choice?.delta?.content;
        if (typeof delta === "string" && delta) opts.onText(delta);
        if (choice?.finish_reason) stats.finishReason = choice.finish_reason;
        if (chunk.usage) {
          stats.promptTokens = chunk.usage.prompt_tokens;
          stats.completionTokens = chunk.usage.completion_tokens;
          stats.cachedTokens = chunk.usage.prompt_tokens_details?.cached_tokens;
          stats.cacheWriteTokens = chunk.usage.prompt_tokens_details?.cache_write_tokens;
          stats.costUsd = Number(chunk.usage.cost ?? 0);
        }
      }
    }
    ok = true;
    return stats;
  } catch (e) {
    error = e instanceof Error ? e.message : String(e);
    throw e;
  } finally {
    stats.totalMs = performance.now() - t0;
    await record({
      at: new Date().toISOString(),
      model: opts.model,
      purpose: opts.purpose,
      pageId: opts.pageId,
      ok,
      // A failed call with unknown billing is charged at the estimate so the budget stays conservative.
      costUsd: local ? 0 : ok ? stats.costUsd : stats.costUsd || (stats.ttfbMs ? estimateUsd(opts.model) : 0),
      promptTokens: stats.promptTokens,
      completionTokens: stats.completionTokens,
      cachedTokens: stats.cachedTokens,
      ms: Math.round(stats.totalMs),
      ttfbMs: stats.ttfbMs === undefined ? undefined : Math.round(stats.ttfbMs),
      provider: local ? "local" : stats.provider,
      reqKb: Math.round(payload.length / 1024),
      retries: stats.retries,
      error,
    });
  }
}

const statusCode = (s: number) => (s === 401 ? "bad-key" : s === 402 ? "no-credit" : s === 429 ? "rate-limit" : s >= 500 ? "provider-down" : "provider");
