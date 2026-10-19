import "./env"; // .env.local sets INPAINT_DEVICE / INPAINT_ENGINE
import type * as ort from "onnxruntime-node";

/** Where inpainting runs: "cpu" (default), or the GPU through DirectML ("dml", Windows) or WebGPU. */
export type InpaintDevice = "cpu" | "dml" | "webgpu";
export const INPAINT_DEVICE = (process.env.INPAINT_DEVICE as InpaintDevice | undefined) ?? "cpu";

/**
 * Which inpainter redraws the art: "auto" (default) uses MI-GAN, and LaMa for holes inside
 * textured art (hatching, screentone) when a GPU is set; "migan" or "lama" force one engine.
 * Measured on the GT pages (tools/eval/src/inpaint-bench.ts): same pixel error, but LaMa
 * continues hatching through a hole where MI-GAN leaves grey ghosts of the letters; LaMa takes
 * ~0.43 s per hole on the GPU against ~0.09 s for MI-GAN, and ~4.9 s against ~0.9 s on the CPU.
 */
export type InpaintEngine = "auto" | "migan" | "lama";
export const INPAINT_ENGINE = (process.env.INPAINT_ENGINE as InpaintEngine | undefined) ?? "auto";

/** LaMa does not run on DirectML (a MatMul in its Fourier units fails): it takes WebGPU instead. */
export const LAMA_DEVICE: InpaintDevice = INPAINT_DEVICE === "dml" ? "webgpu" : INPAINT_DEVICE;

/** Session options for a device; DirectML needs sequential execution without memory patterns. */
export function sessionOptions(device: InpaintDevice): ort.InferenceSession.SessionOptions {
  if (device === "cpu") return { executionProviders: ["cpu"], intraOpNumThreads: 4 };
  return { executionProviders: [device, "cpu"], enableMemPattern: false, executionMode: "sequential" };
}
