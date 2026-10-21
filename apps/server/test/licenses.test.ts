import { describe, expect, it } from "vitest";
import { LAMA_MODELS } from "../src/lama";
import { assertModelAllowed, creditLines, licenseOf, modelAllowed, MODEL_LICENSES } from "../src/licenses";

describe("model licences", () => {
  it("has one record per id", () => {
    const ids = MODEL_LICENSES.map((m) => m.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("covers every model a loader can ask for", () => {
    for (const id of ["detector", "comic-text-detector", "comic-text-mask", "migan", "aot", ...Object.keys(LAMA_MODELS)]) expect(licenseOf(id), id).toBeDefined();
  });

  it("allows everything outside the paid tier", () => {
    expect(modelAllowed("ocr/cpt-flex", false)).toBe(true);
    expect(modelAllowed("unknown-model", false)).toBe(true);
  });

  it("keeps non-commercial, unreviewed and unknown models out of the paid tier", () => {
    expect(modelAllowed("ocr/cpt-flex", true)).toBe(false);
    expect(modelAllowed("ocr/lt-m109-academic", true)).toBe(false);
    expect(modelAllowed("lama-mpe", true)).toBe(false);
    expect(modelAllowed("unknown-model", true)).toBe(false);
    expect(() => assertModelAllowed("ocr/lt-m109-academic", true)).toThrow(/academic/);
  });

  it("allows cleared models and lists the notices the app must show", () => {
    expect(modelAllowed("migan", true)).toBe(true);
    expect(modelAllowed("ocr/baberu", true)).toBe(true);
    const lines = creditLines(["migan", "ocr/baberu", "comic-text-detector"]);
    expect(lines).toHaveLength(2);
    expect(lines.every((l) => l.includes("Manga109-s"))).toBe(true);
  });

  it("gives every credit-only model its notice", () => {
    for (const m of MODEL_LICENSES.filter((x) => x.commercial === "credit")) expect(m.credit, m.id).toBeTruthy();
  });
});
