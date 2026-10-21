// Decoder worker for the crop OCR (ocr.ts): onnxruntime-node runs each call synchronously on its thread,
// so crops are decoded in parallel on worker threads, each with its own CPU sessions. Plain JS so it loads
// without the TypeScript loader. Same decode as Baberu's onnx_infer.py: greedy, repetition penalty 1.2,
// run caps 12 (letters, kana, kanji, digits) and 16 (symbols).
import { parentPort, workerData } from "node:worker_threads";
import * as ort from "onnxruntime-node";

const BOS = 1;
const EOS = 2;
const LAYERS = 6;
const MAX_TOKENS = 256;
const REPETITION_PENALTY = 1.2;
const MAX_CONTENT_RUN = 12;
const MAX_SYMBOL_RUN = 16;

const opts = { executionProviders: ["cpu"], intraOpNumThreads: workerData.threads, graphOptimizationLevel: "all" };
const prefill = await ort.InferenceSession.create(new Uint8Array(workerData.prefill), opts);
const step = await ort.InferenceSession.create(new Uint8Array(workerData.step), opts);
const content = new Set(workerData.content);

function lastLogits(t) {
  const [, seq, vocab] = t.dims;
  return Float64Array.from(t.data.subarray((seq - 1) * vocab, seq * vocab));
}

async function decode(embeds, dims) {
  const vis = new ort.Tensor("float32", embeds, dims);
  let out = await prefill.run({ vision_embeds: vis, input_ids: new ort.Tensor("int64", BigInt64Array.from([BigInt(BOS)]), [1, 1]) });
  let logits = lastLogits(out.logits);
  const seen = new Set([BOS]);
  const toks = [];
  let pos = dims[1] + 1;
  for (let n = 0; n < MAX_TOKENS; n++) {
    for (const id of seen) logits[id] = logits[id] < 0 ? logits[id] * REPETITION_PENALTY : logits[id] / REPETITION_PENALTY;
    const last = toks.length ? toks[toks.length - 1] : 0;
    const cap = content.has(last) ? MAX_CONTENT_RUN : last > 3 ? MAX_SYMBOL_RUN : 0;
    if (cap) {
      let run = 0;
      for (let i = toks.length - 1; i >= 0 && toks[i] === last; i--) run++;
      if (run >= cap) logits[last] = -Infinity;
    }
    let next = 0;
    for (let i = 1; i < logits.length; i++) if (logits[i] > logits[next]) next = i;
    if (next === EOS) break;
    toks.push(next);
    seen.add(next);
    if (toks.length >= MAX_TOKENS) break;
    const feed = {
      input_ids: new ort.Tensor("int64", BigInt64Array.from([BigInt(next)]), [1, 1]),
      position_ids: new ort.Tensor("int64", BigInt64Array.from([BigInt(pos)]), [1, 1]),
    };
    for (let l = 0; l < LAYERS; l++) {
      feed[`past_k${l}`] = out[`present_k${l}`];
      feed[`past_v${l}`] = out[`present_v${l}`];
    }
    out = await step.run(feed);
    logits = lastLogits(out.logits);
    pos++;
  }
  return toks;
}

parentPort.on("message", async ({ id, embeds, dims }) => {
  try {
    parentPort.postMessage({ id, toks: await decode(embeds, dims) });
  } catch (e) {
    parentPort.postMessage({ id, error: String(e?.message ?? e) });
  }
});
parentPort.postMessage({ ready: true });
