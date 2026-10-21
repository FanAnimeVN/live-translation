import { describe, expect, it } from "vitest";
import { buildUserParts, type PromptInput, type TextRegion } from "../src";

const regions: TextRegion[] = [
  { id: "r1", kind: "bubble", box: { x: 10, y: 10, w: 50, h: 80 }, members: [], score: 0.9, order: 0 },
  { id: "r2", kind: "bubble", box: { x: 100, y: 10, w: 50, h: 80 }, members: [], score: 0.9, order: 1 },
];
const base: PromptInput = {
  title: "Test",
  position: { chapter: 1, page: 1 },
  stableMemory: "(none)",
  volatileMemory: "(first page read)",
  regions,
  image: { w: 400, h: 600 },
  markedPageDataUrl: "data:image/jpeg;base64,AAAA",
  crops: [],
};

describe("OCR-first reading in the page prompt", () => {
  it("sends the page image and no OCR block by default", () => {
    const parts = buildUserParts(base);
    expect(parts.filter((p) => p.type === "image")).toHaveLength(1);
    expect(parts.some((p) => p.type === "text" && p.text.includes("dedicated OCR model"))).toBe(false);
  });

  it("adds the pre-read text next to the image (ocr+image)", () => {
    const parts = buildUserParts({ ...base, preRead: { r1: "こんにちは", r2: "" } });
    const hint = parts.find((p) => p.type === "text" && p.text.startsWith("Pre-read"));
    expect(hint && hint.type === "text" && hint.text).toContain("r1: こんにちは");
    expect(hint && hint.type === "text" && hint.text).toContain("r2: (nothing read)");
    expect(parts.filter((p) => p.type === "image")).toHaveLength(1);
  });

  it("sends no page image in OCR-only mode but keeps face references", () => {
    const parts = buildUserParts({
      ...base,
      markedPageDataUrl: undefined,
      preRead: { r1: "a", r2: "b" },
      castRefs: [{ name: "Kenta", ja: "健太", dataUrl: "data:image/jpeg;base64,BBBB" }],
    });
    const images = parts.filter((p) => p.type === "image");
    expect(images).toHaveLength(1);
    expect(images[0].type === "image" && images[0].dataUrl).toContain("BBBB");
    expect(parts.some((p) => p.type === "text" && p.text.startsWith("No page image is attached"))).toBe(true);
  });
});
