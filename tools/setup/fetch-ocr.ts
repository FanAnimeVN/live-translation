/**
 * Download the crop OCR used by "OCR first" reading (apps/server/src/ocr.ts): Baberu OCR v1.2 ONNX files
 * at a pinned revision, each checked against its SHA-256 before it is kept. Weights and vocabulary only.
 *
 *   npm run models:ocr
 */
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { ROOT } from "@lt/server";

const REPO = "genshiai-daichi/baberu-ocr";
const REV = "b9868433dbda3ed9ba1357d008599ff4ada873d5";
const FILES: Record<string, string> = {
  "onnx/vision_int4.onnx": "1967ecef502e4c1e1e7c512ea0a2e06396b39ded87a8a9cc77bd7db2e981a361",
  "onnx/decoder_prefill_int8.onnx": "187a59cb61d3870f1f97c9eb027eb34ff19d023fba801cda113a13870be0b724",
  "onnx/decoder_step_int8.onnx": "46640b0b3db77f0f0eef660bbe5dc9126a5e0fb49eb2786b2edba7b0371d9769",
  "tokenizer/vocab.json": "681de4eb83154a397af49e2ddae4705041b12a22e16fe00860b829e889e5f47c",
  LICENSE: "186332043e82fcfdbeb0b8e0e8d77b63d97ffa3dd9d91ccf7cef1377d8ab345b",
};
const dir = join(ROOT, "models", "ocr", "baberu", REV);
const sha = (b: Uint8Array) => createHash("sha256").update(b).digest("hex");

for (const [file, want] of Object.entries(FILES)) {
  const path = join(dir, file);
  const have = await readFile(path).catch(() => undefined);
  if (have && sha(have) === want) {
    console.log(`ok       ${file}`);
    continue;
  }
  const res = await fetch(`https://huggingface.co/${REPO}/resolve/${REV}/${file}`);
  if (!res.ok) throw new Error(`${file}: HTTP ${res.status}`);
  const bytes = new Uint8Array(await res.arrayBuffer());
  if (sha(bytes) !== want) throw new Error(`${file}: checksum mismatch, not saved`);
  await mkdir(dirname(path), { recursive: true });
  await writeFile(path, bytes);
  console.log(`fetched  ${file} (${(bytes.length / 1e6).toFixed(1)} MB)`);
}
console.log(`Baberu OCR ready in ${dir}`);
