import type { TextRegion } from "@lt/core";

/**
 * Offline stand-in for the model, used to develop and test rendering without API
 * cost. Output is clearly fake Vietnamese of realistic lengths; never shown as a result.
 */
const SAMPLES = [
  "[mẫu] Hôm nay cũng được một mẻ lớn đấy!",
  "[mẫu] Khoan đã… nghe tớ nói hết đã nào.",
  "[mẫu] Thật á?!",
  "[mẫu] Không phải lỗi của cậu đâu, đừng tự trách mình nữa.",
  "[mẫu] Ừm.",
  "[mẫu] Chủ nhân ơi, nhìn em này~!",
  "[mẫu] Lần sau nhất định phải cẩn thận hơn đấy nhé.",
];

export async function* mockReply(regions: TextRegion[], onlyIds?: string[]): AsyncGenerator<string> {
  const ids = onlyIds ?? regions.map((r) => r.id);
  await sleep(400);
  for (const [i, id] of ids.entries()) {
    const line = JSON.stringify({
      id,
      ja: "",
      role: "dialogue",
      speaker: "unknown",
      to: "unknown",
      vi: SAMPLES[i % SAMPLES.length],
      style: [],
    });
    // Split each line into chunks to exercise the streaming parser.
    for (let k = 0; k < line.length; k += 23) {
      yield line.slice(k, k + 23);
      await sleep(8);
    }
    yield "\n";
  }
  yield JSON.stringify({ type: "notes", names: [], address: [], missed: [] }) + "\n";
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
