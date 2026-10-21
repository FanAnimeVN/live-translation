/**
 * Licence and training-data record for every model the product can load. The paid tier (PAID_TIER=1)
 * refuses models whose use there is not cleared: "no" (non-commercial licence or training data, e.g. full
 * Manga109) and "review" (training data unknown, or a claim not checked yet). Models marked "credit" are
 * allowed when their notice is shown (creditLines()), e.g. models trained on Manga109-s, whose terms allow
 * commercial use of results, pre-trained models included, if the use of Manga109-s is indicated.
 *
 * Add every new model (and every checkpoint we train) here before loading it: id, source, licence,
 * training data, and the commercial status with its reason.
 */
export type Commercial = "yes" | "credit" | "review" | "no";

export interface ModelLicense {
  id: string;
  /** Where the weights come from (repo @ revision or release). */
  source: string;
  license: string;
  trainingData: string;
  commercial: Commercial;
  /** Notice to show in the app's credits when commercial is "credit". */
  credit?: string;
  why: string;
}

const M109S = "Trained with the Manga109-s dataset (courtesy of the authors; http://www.manga109.org)";

export const MODEL_LICENSES: ModelLicense[] = [
  // Page detection and text masks
  { id: "detector", source: "ogkalu/comic-text-and-bubble-detector @ 16e8a622", license: "Apache-2.0", trainingData: "not stated by the author", commercial: "review", why: "licence allows it; training data unknown, ask the author before the paid launch" },
  { id: "comic-text-detector", source: "manga-image-translator release beta-0.3 (dmMaze/comic-text-detector)", license: "GPL-3.0", trainingData: "Manga109-s, Digital Comic Museum, synthetic pages", commercial: "credit", credit: `comic-text-detector (GPL-3.0). ${M109S}`, why: "Manga109-s terms allow commercial use of results with the dataset indicated; GPL-3.0 needs our source published (it is)" },
  { id: "comic-text-mask", source: "TareHimself/comic-text-mask @ ebd37f1a", license: "MIT", trainingData: "not stated", commercial: "review", why: "training data unknown" },
  // Inpainting
  { id: "migan", source: "andraniksargsyan/migan @ 406830d0 (Picsart AI Research)", license: "MIT", trainingData: "Places2 / CelebA-HQ (paper)", commercial: "yes", why: "MIT, public photo datasets" },
  { id: "lama", source: "Carve/LaMa-ONNX @ c3c0c9e4 (big-lama)", license: "Apache-2.0", trainingData: "Places2 (paper)", commercial: "yes", why: "Apache-2.0" },
  { id: "lama-cv", source: "opencv/inpainting_lama @ aee6d22f", license: "Apache-2.0", trainingData: "Places2 (paper)", commercial: "yes", why: "Apache-2.0" },
  { id: "lama-manga", source: "dreMaz/AnimeMangaInpainting @ 2953a4e9", license: "MIT", trainingData: "manga/anime images, not listed", commercial: "review", why: "training images not listed" },
  { id: "lama-mpe", source: "manga-image-translator release beta-0.3", license: "GPL-3.0 project", trainingData: "not stated", commercial: "review", why: "training data unknown" },
  { id: "aot", source: "manga-image-translator release beta-0.3", license: "GPL-3.0 project", trainingData: "not stated", commercial: "review", why: "training data unknown" },
  // Crop OCR (measured in docs/LOCAL-MODELS.md; not wired into the product yet)
  { id: "ocr/baberu", source: "genshiai-daichi/baberu-ocr v1.2", license: "Apache-2.0", trainingData: "Manga109-s", commercial: "credit", credit: `Baberu OCR (Apache-2.0). ${M109S}`, why: "Manga109-s results allowed with the dataset indicated" },
  { id: "ocr/manga-ocr", source: "kha-white/manga-ocr-base", license: "Apache-2.0", trainingData: "Manga109-s and synthetic text", commercial: "credit", credit: `manga-ocr (Apache-2.0). ${M109S}`, why: "Manga109-s results allowed with the dataset indicated" },
  { id: "ocr/cpt-flex", source: "muscgab/manga-ocr-base-CPT-flex", license: "CC BY-NC-SA 4.0", trainingData: "AnimeText-OCR (NC) and synthetic", commercial: "no", why: "non-commercial licence; free local mode only" },
  { id: "ocr/nar-small", source: "muscgab/manga-ocr-nar-small", license: "CC BY-NC-SA 4.0", trainingData: "AnimeText-OCR (NC) and synthetic", commercial: "no", why: "non-commercial licence; free local mode only" },
  { id: "ocr/lt-m109-academic", source: "our fine-tune of manga-ocr-base (tools/kaggle/train-ocr.py)", license: "ours", trainingData: "full Manga109 (academic licence)", commercial: "no", why: "Manga109 is academic use only: thesis numbers, never the paid tier" },
  // Local translation / reading models (run on the reader's own machine)
  { id: "local/hy-mt2", source: "tencent/Hy-MT2-7B(-GGUF), 1.8B", license: "Apache-2.0", trainingData: "Tencent (not listed)", commercial: "yes", why: "Apache-2.0" },
  { id: "local/gemma4", source: "google/gemma-4 (Ollama gemma4)", license: "Apache-2.0", trainingData: "Google", commercial: "yes", why: "Apache-2.0" },
  { id: "local/qwen3.5", source: "Qwen/Qwen3.5 (Ollama qwen3.5)", license: "Apache-2.0", trainingData: "Alibaba", commercial: "yes", why: "Apache-2.0" },
  { id: "local/translategemma", source: "google/translategemma", license: "Gemma Terms of Use", trainingData: "Google", commercial: "yes", why: "Gemma terms allow commercial use under the use policy" },
];

export const PAID_TIER = process.env.PAID_TIER === "1";

export function licenseOf(id: string): ModelLicense | undefined {
  return MODEL_LICENSES.find((m) => m.id === id);
}

/** May this model run in the given tier? Unknown ids are never allowed in the paid tier. */
export function modelAllowed(id: string, paid = PAID_TIER): boolean {
  if (!paid) return true;
  const c = licenseOf(id)?.commercial;
  return c === "yes" || c === "credit";
}

export function assertModelAllowed(id: string, paid = PAID_TIER): void {
  if (modelAllowed(id, paid)) return;
  const l = licenseOf(id);
  throw new Error(`Model "${id}" is not cleared for the paid tier (${l ? `${l.commercial}: ${l.why}` : "no licence record"}); see apps/server/src/licenses.ts`);
}

/** Notices the app must show for the models it uses in this tier. */
export function creditLines(ids: string[]): string[] {
  return ids.map(licenseOf).filter((l): l is ModelLicense => !!l?.credit).map((l) => l.credit!);
}
