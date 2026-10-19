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

  it("keeps speed lines that a burst balloon open at the top lets the fill slip between", () => {
    const img = image(120, 120);
    for (let x = 10; x < 110; x++) {
      if (x < 40 || x > 80) set(img, x, 10, 0); // outline with an opening at the top
      set(img, x, 109, 0);
    }
    for (let y = 10; y < 110; y++) {
      set(img, 10, y, 0);
      set(img, 109, y, 0);
    }
    for (let x = 44; x <= 76; x += 8) for (let y = 14; y < 48; y++) set(img, x, y, 0); // speed lines inside the opening
    rect(img, 56, 62, 8, 30, 0); // glyph column
    const r = bubbleInterior(img, { x: 8, y: 10, w: 104, h: 102 }, [255, 255, 255]); // the box top runs along the outline
    expect(r).not.toBeNull();
    expect(get(img, 60, 75)).toBe(255); // glyph erased
    expect(get(img, 52, 30)).toBe(0); // speed line kept
  });

  it("erases a caption box on dark art even when the text fills it edge to edge", () => {
    const img = image(140, 200, 40); // dark art around the caption
    rect(img, 20, 20, 100, 160, 0); // black border
    rect(img, 23, 23, 94, 154, 250); // white caption paper
    for (let k = 0; k < 6; k++) rect(img, 28 + k * 15, 28, 6, 144, 10); // columns reaching the border
    const report = eraseRegion(img, [{ x: 24, y: 24, w: 92, h: 152 }], { bubble: { x: 16, y: 16, w: 108, h: 168 }, charSize: 14 });
    expect(report.mode).toBe("box");
    expect(report.interior).toBeDefined();
    expect(get(img, 30, 100)).toBe(250); // text gone, paper colour kept
    expect(get(img, 21, 100)).toBe(0); // border kept
    expect(get(img, 8, 100)).toBe(40); // art outside kept
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

/** A pen-drawn "口"-like glyph: 2 px strokes around an empty middle. */
const glyph = (img: RGBAImage, x: number, y: number, s: number, v = 15) => {
  rect(img, x, y, s, 2, v);
  rect(img, x, y + s - 2, s, 2, v);
  rect(img, x, y, 2, s, v);
  rect(img, x + s - 2, y, 2, s, v);
};
const disc = (img: RGBAImage, cx: number, cy: number, r: number, v: number) => {
  for (let y = cy - r; y <= cy + r; y++) for (let x = cx - r; x <= cx + r; x++) if ((x - cx) ** 2 + (y - cy) ** 2 <= r * r) set(img, x, y, v);
};

describe("artTextMask", () => {
  it("covers glyph strokes but not long line art crossing the text box", () => {
    const img = image(200, 200, 180); // mid-grey art background
    for (let y = 0; y < 200; y++) set(img, 100, y, 20); // long vertical art line through the box
    glyph(img, 60, 60, 16); // glyph 1 (with light halo above)
    rect(img, 58, 56, 20, 2, 245);
    glyph(img, 60, 90, 16); // glyph 2
    const job = artTextMask(img, [{ x: 55, y: 55, w: 60, h: 60 }], { charSize: 18 });
    const at = (x: number, y: number) => job.hole[(y - job.crop.y) * job.crop.w + (x - job.crop.x)];
    expect(job.rect).toBe(false);
    expect(at(60, 68)).toBe(1);
    expect(at(68, 104)).toBe(1);
    expect(at(100, 85)).toBe(0); // the art line stays out of the hole
    expect(job.coverage).toBeGreaterThan(0.05);
    expect(job.coverage).toBeLessThan(0.85);
  });

  it("flags display lettering drawn with thick brush strokes so it stays part of the art", () => {
    const img = image(200, 120, 200);
    for (let k = 0; k < 3; k++) rect(img, 30 + k * 50, 30, 30, 60, 10); // three heavy strokes
    const job = artTextMask(img, [{ x: 24, y: 24, w: 160, h: 72 }], { charSize: 60 });
    expect(job.bold).toBe(true);
    const thin = image(200, 120, 200);
    for (let k = 0; k < 3; k++) glyph(thin, 30 + k * 50, 30, 30);
    expect(artTextMask(thin, [{ x: 24, y: 24, w: 160, h: 72 }], { charSize: 32 }).bold).toBe(false);
  });

  it("leaves hatching that the text box covers out of the hole and still removes the letters", () => {
    const img = image(220, 240, 250);
    // diagonal hatching over the top of the page, reaching 25 px into the text box
    for (let x0 = -60; x0 < 220; x0 += 6)
      for (let t = 0; t < 22; t++)
        for (const y0 of [2, 24, 46]) {
          const x = x0 + y0 + Math.round(t * 0.7);
          const y = y0 + Math.round(t * 0.7);
          if (x >= 0 && x < 219 && y < 62) rect(img, x, y, 2, 2, 20);
        }
    for (let k = 0; k < 4; k++) glyph(img, 78, 80 + k * 28, 20); // a column of letters under the shading
    const box = [{ x: 72, y: 38, w: 34, h: 160 }];
    const job = artTextMask(img, box, { charSize: 22 });
    const at = (x: number, y: number) => job.hole[(y - job.crop.y) * job.crop.w + (x - job.crop.x)];
    expect(at(78, 90)).toBe(1); // letter removed
    let hatchIn = 0, hatchHole = 0;
    for (let y = 40; y < 60; y++)
      for (let x = 74; x < 104; x++)
        if (get(img, x, y) < 100) {
          hatchIn++;
          hatchHole += at(x, y);
        }
    expect(hatchIn).toBeGreaterThan(30);
    expect(hatchHole / hatchIn).toBeLessThan(0.1); // the shading inside the box stays art
  });

  it("still removes a vertical dash that sits in line under vertical speed lines", () => {
    const img = image(200, 220, 250);
    for (let x = 2; x < 200; x += 6) rect(img, x, 0, 2, 66, 20); // vertical speed lines above the text
    rect(img, 92, 70, 2, 20, 15); // "ー" of vertical text, right under a speed line
    for (let k = 0; k < 3; k++) glyph(img, 83, 98 + k * 26, 20);
    const job = artTextMask(img, [{ x: 80, y: 68, w: 28, h: 130 }], { charSize: 22 });
    expect(job.hole[(80 - job.crop.y) * job.crop.w + (92 - job.crop.x)]).toBe(1);
  });

  it("keeps a filled eye beside small handwriting out of the hole, even in the whole-box fallback", () => {
    const img = image(160, 160, 235); // pale art (a hand, a face)
    for (let k = 0; k < 4; k++) glyph(img, 50, 40 + k * 12, 9); // a column of small handwriting
    disc(img, 54, 92, 4, 10); // the eye of a small animal right under the text
    const box = [{ x: 46, y: 36, w: 20, h: 64 }]; // a loose detector box that takes the eye in
    const job = artTextMask(img, box, { charSize: 16 });
    const at = (x: number, y: number) => job.hole[(y - job.crop.y) * job.crop.w + (x - job.crop.x)];
    expect(at(50, 44)).toBe(1); // handwriting removed
    expect(at(54, 92)).toBe(0); // the eye is art
    const fallback = artTextMask(img, box, { charSize: 16, rect: true });
    expect(fallback.hole[(92 - fallback.crop.y) * fallback.crop.w + (54 - fallback.crop.x)]).toBe(0);
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
