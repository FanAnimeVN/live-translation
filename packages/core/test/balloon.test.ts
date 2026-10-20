import { describe, expect, it } from "vitest";
import { adoptBalloons, findBalloon, paintBalloon, type RGBAImage, type TextRegion } from "../src";

/** Synthetic pages only (no manga images in tests): a small white balloon on hatching. */
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

/**
 * A page-sized image (a balloon is small next to the page) with hatching in its corner, and on it a
 * white ellipse (centre 100,100, radii 40x50) with a 3 px black outline.
 */
function balloonOnHatching(): RGBAImage {
  const img = image(1100, 1100);
  for (let y = 0; y < 220; y++) for (let x = 0; x < 220; x++) if ((x + y) % 5 < 2) set(img, x, y, 20);
  for (let y = 0; y < 200; y++)
    for (let x = 0; x < 200; x++) {
      const d = Math.hypot((x - 100) / 40, (y - 100) / 50);
      if (d <= 1) set(img, x, y, 255);
      if (d > 1 - 3 / 45 && d <= 1) set(img, x, y, 0);
    }
  return img;
}
// Text fills most of a small balloon (as in the missed ones on real pages).
const textBox = { x: 72, y: 62, w: 56, h: 76 };
const strokes = (img: RGBAImage) => {
  rect(img, 84, 70, 4, 60, 0);
  rect(img, 98, 70, 4, 60, 0);
  rect(img, 112, 70, 4, 60, 0);
};
const region = (box = textBox, id = "r1"): TextRegion => ({ id, kind: "free", box, members: [box], score: 0.5, order: 0 });

describe("findBalloon", () => {
  it("finds a small round balloon the detector missed, around its text", () => {
    const img = balloonOnHatching();
    strokes(img);
    const b = findBalloon(img, region());
    expect(b).toBeDefined();
    expect(Math.abs(b!.x - 60)).toBeLessThanOrEqual(5);
    expect(Math.abs(b!.y + b!.h - 150)).toBeLessThanOrEqual(5);
    const [adopted] = adoptBalloons(img, [region()]);
    expect(adopted.kind).toBe("bubble");
    expect(adopted.bubble).toEqual(b);
  });

  it("rejects text on open paper and a closed area with a drawing inside", () => {
    const page = image(1100, 1100);
    rect(page, 98, 70, 4, 60, 0);
    expect(findBalloon(page, region())).toBeUndefined();
    // White area of art closed by line work: a drawing (a face, a prop) beside the text inside it.
    const img = balloonOnHatching();
    rect(img, 108, 70, 4, 60, 0);
    rect(img, 116, 70, 4, 60, 0);
    for (let y = 88; y < 112; y++) for (let x = 64; x < 88; x++) if (Math.abs(Math.hypot(x - 76, y - 100) - 10) < 1.5) set(img, x, y, 0);
    expect(findBalloon(img, region({ x: 104, y: 62, w: 20, h: 76 }))).toBeUndefined();
  });

  it("leaves boxes the reader model reported as missed text alone (loose boxes)", () => {
    const img = balloonOnHatching();
    strokes(img);
    expect(adoptBalloons(img, [region(textBox, "m1")])[0].bubble).toBeUndefined();
  });
});

describe("paintBalloon", () => {
  it("repaints strokes that touch the outline, keeps the outline and the hatching outside", () => {
    const img = balloonOnHatching();
    strokes(img);
    rect(img, 61, 98, 25, 4, 0); // a stroke running into the outline
    const ok = paintBalloon(img, { x: 57, y: 47, w: 86, h: 106 }, [{ x: 62, y: 62, w: 66, h: 76 }], [255, 255, 255], 20);
    expect(ok).toBe(true);
    expect(get(img, 99, 100)).toBe(255);
    expect(get(img, 75, 100)).toBe(255);
    expect(get(img, 100, 51)).toBeLessThan(60); // outline at the top
    let hatching = 0;
    for (let x = 0; x < 40; x++) if (get(img, x, 10) < 60) hatching++;
    expect(hatching).toBeGreaterThan(10);
  });

  it("refuses a balloon open to the page (paper runs out of the box)", () => {
    const img = image(200, 200);
    strokes(img);
    expect(paintBalloon(img, { x: 57, y: 47, w: 86, h: 106 }, [textBox], [255, 255, 255], 20)).toBe(false);
  });
});
