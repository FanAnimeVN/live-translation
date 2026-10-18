import { describe, expect, it } from "vitest";
import { artTextMask, bubbleInterior, eraseRegion, isLineLike, type RGBAImage } from "../src";

/** Synthetic grey image helpers (no manga images in tests). */
function image(w: number, h: number, fill = 255): RGBAImage {
  const data = new Uint8ClampedArray(w * h * 4);
  for (let i = 0; i < data.length; i += 4) {
    data[i] = data[i + 1] = data[i + 2] = fill;
    data[i + 3] = 255;
  }
  return { width: w, height: h, data };
}
const set = (img: RGBAImage, x: number, y: number, v: number) => {
  const i = (y * img.width + x) * 4;
  img.data[i] = img.data[i + 1] = img.data[i + 2] = v;
};
const get = (img: RGBAImage, x: number, y: number) => img.data[(y * img.width + x) * 4];
const rect = (img: RGBAImage, x: number, y: number, w: number, h: number, v: number) => {
  for (let yy = y; yy < y + h; yy++) for (let xx = x; xx < x + w; xx++) set(img, xx, yy, v);
};

describe("bubbleInterior", () => {
  it("repaints only inside a closed outline: outline and lines outside survive", () => {
    const img = image(120, 120);
    // diagonal "speed line" in the box corner, outside the balloon
    for (let k = 0; k < 25; k++) set(img, 2 + k, 2 + k, 0);
    // elliptical outline
    for (let a = 0; a < 720; a++) {
      const t = (a / 720) * Math.PI * 2;
      set(img, Math.round(60 + 52 * Math.cos(t)), Math.round(60 + 52 * Math.sin(t)), 0);
    }
    rect(img, 50, 40, 8, 30, 10); // glyph column inside
    const r = bubbleInterior(img, { x: 4, y: 4, w: 112, h: 112 }, [255, 255, 255]);
    expect(r).not.toBeNull();
    expect(get(img, 54, 55)).toBe(255); // glyph erased
    expect(get(img, 112, 60)).toBe(0); // outline kept
    expect(get(img, 10, 10)).toBe(0); // speed line outside kept
  });

  it("refuses an open outline instead of flooding the page", () => {
    const img = image(80, 80);
    rect(img, 30, 30, 6, 20, 0); // glyphs, no outline at all
    expect(bubbleInterior(img, { x: 0, y: 0, w: 80, h: 80 }, [255, 255, 255])).toBeNull();
  });
});

describe("isLineLike", () => {
  it("separates hair-thin long strokes from glyphs and dashes", () => {
    expect(isLineLike(80, 80, 120, 20)).toBe(true); // diagonal speed line
    expect(isLineLike(18, 3, 40, 20)).toBe(false); // long-vowel dash "ー"
    expect(isLineLike(20, 20, 160, 20)).toBe(false); // compact glyph
  });
});

describe("artTextMask", () => {
  it("covers glyph strokes but not long line art crossing the text box", () => {
    const img = image(200, 200, 180); // mid-grey art background
    for (let y = 0; y < 200; y++) set(img, 100, y, 20); // long vertical art line through the box
    rect(img, 60, 60, 16, 16, 15); // glyph 1 (with light halo below)
    rect(img, 58, 58, 20, 2, 245);
    rect(img, 60, 90, 16, 16, 15); // glyph 2
    const job = artTextMask(img, [{ x: 55, y: 55, w: 60, h: 60 }], { charSize: 18 });
    const at = (x: number, y: number) => job.hole[(y - job.crop.y) * job.crop.w + (x - job.crop.x)];
    expect(at(68, 68)).toBe(1);
    expect(at(68, 98)).toBe(1);
    expect(at(100, 85)).toBe(0); // the art line stays out of the hole
    expect(job.coverage).toBeGreaterThan(0.05);
    expect(job.coverage).toBeLessThan(0.85);
  });
});

describe("eraseRegion safety", () => {
  it("on busy hatching either restores the exact source or removes the glyph (never a half state)", () => {
    const img = image(160, 160);
    for (let y = 0; y < 160; y++) for (let x = 0; x < 160; x++) if (x % 6 < 2) set(img, x, y, 30); // hatching
    rect(img, 60, 60, 30, 30, 255); // paper behind the text, like a halo block
    rect(img, 66, 66, 6, 18, 0);
    rect(img, 78, 66, 6, 18, 0);
    const before = Uint8ClampedArray.from(img.data);
    const report = eraseRegion(img, [{ x: 58, y: 58, w: 34, h: 34 }], { mode: "glyph", charSize: 16 });
    if (report.mode === "skipped") expect(Array.from(img.data)).toEqual(Array.from(before));
    else expect(get(img, 68, 70)).toBe(255);
  });

  it("erases glyphs inside a plain bubble and keeps its outline", () => {
    const img = image(100, 100);
    for (let x = 10; x < 90; x++) {
      set(img, x, 10, 0);
      set(img, x, 89, 0);
    }
    for (let y = 10; y < 90; y++) {
      set(img, 10, y, 0);
      set(img, 89, y, 0);
    }
    rect(img, 40, 30, 8, 30, 0);
    const report = eraseRegion(img, [{ x: 36, y: 26, w: 16, h: 38 }], { bubble: { x: 8, y: 8, w: 84, h: 84 }, charSize: 14 });
    expect(report.mode).toBe("box");
    expect(get(img, 44, 45)).toBe(255);
    expect(get(img, 10, 50)).toBe(0);
  });
});
