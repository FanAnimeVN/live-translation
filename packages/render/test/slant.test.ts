import { describe, expect, it } from "vitest";
import { expand, type Box, type RegionTranslation, type RGBAImage, type TextRegion } from "@lt/core";
import { renderTranslation, type Ctx2D } from "../src";
import { arcBow, avoidAreas, frameHas, placeOnArc, textSlant, type Slant } from "../src/slant";

/** A canvas stand-in over `img`: drawing is a no-op, text is monospace (0.55 em per character). */
function ctxOver(img: RGBAImage): Ctx2D {
  const ctx = {
    font: "",
    fillStyle: "",
    strokeStyle: "",
    lineWidth: 1,
    lineJoin: "",
    textAlign: "",
    textBaseline: "",
    globalAlpha: 1,
    measureText: (t: string) => ({ width: [...t].length * Number(/(\d+)px/.exec(ctx.font)?.[1] ?? 10) * 0.55 }),
    getImageData: () => img,
  };
  for (const k of ["fillText", "strokeText", "fillRect", "strokeRect", "putImageData", "save", "restore", "translate", "rotate", "drawImage"]) {
    (ctx as Record<string, unknown>)[k] = () => {};
  }
  return ctx as unknown as Ctx2D;
}
const tr = (id: string, ja: string, vi: string): RegionTranslation => ({ id, ja, vi, role: "sign", speaker: "", to: "", style: [], seq: 0, fixes: [] });
const inkBounds = (img: RGBAImage): Box => {
  let x0 = Infinity, y0 = Infinity, x1 = -1, y1 = -1;
  for (let y = 0; y < img.height; y++)
    for (let x = 0; x < img.width; x++)
      if (img.data[(y * img.width + x) * 4] < 100) {
        x0 = Math.min(x0, x);
        y0 = Math.min(y0, y);
        x1 = Math.max(x1, x);
        y1 = Math.max(y1, y);
      }
  return { x: x0, y: y0, w: x1 - x0 + 1, h: y1 - y0 + 1 };
};

function image(w: number, h: number, fill = 250): RGBAImage {
  const data = new Uint8ClampedArray(w * h * 4).fill(fill);
  for (let i = 3; i < data.length; i += 4) data[i] = 255;
  return { width: w, height: h, data };
}
const dot = (img: RGBAImage, x: number, y: number, v = 15) => {
  const xi = Math.round(x), yi = Math.round(y);
  if (xi < 0 || yi < 0 || xi >= img.width || yi >= img.height) return;
  const i = (yi * img.width + xi) * 4;
  img.data[i] = img.data[i + 1] = img.data[i + 2] = v;
};
/** A pen-drawn "口"-like glyph of size s centred at (cx, cy), turned by `a` radians. */
function glyph(img: RGBAImage, cx: number, cy: number, s: number, a: number) {
  const c = Math.cos(a), sn = Math.sin(a);
  for (let u = -s / 2; u <= s / 2; u += 0.5)
    for (const v of [-s / 2, -s / 2 + 1, s / 2 - 1, s / 2]) {
      for (const [p, q] of [[u, v], [v, u]]) dot(img, cx + p * c - q * sn, cy + p * sn + q * c);
    }
}
/** Rows x cols glyph grid (pitch 1.25 s) centred at (cx, cy), the whole grid turned by `a`. */
function block(img: RGBAImage, cx: number, cy: number, rows: number, cols: number, s: number, a: number) {
  const c = Math.cos(a), sn = Math.sin(a);
  const pitch = s * 1.25;
  for (let r = 0; r < rows; r++)
    for (let k = 0; k < cols; k++) {
      const u = (k - (cols - 1) / 2) * pitch, v = (r - (rows - 1) / 2) * pitch;
      glyph(img, cx + u * c - v * sn, cy + u * sn + v * c, s, a);
    }
}

describe("textSlant", () => {
  it("reads the angle of a tilted block of text (a card or sign drawn at an angle)", () => {
    for (const deg of [-14, 9, 22]) {
      const img = image(400, 300);
      const a = (deg * Math.PI) / 180;
      block(img, 200, 150, 3, 9, 16, a);
      const s = textSlant(img, [{ x: 40, y: 40, w: 320, h: 220 }], 16);
      expect(s, `${deg} deg`).toBeDefined();
      expect(Math.abs((s!.angle * 180) / Math.PI - deg), `${deg} deg`).toBeLessThan(1.6);
      expect(s!.cx).toBeCloseTo(200, -1);
      // The deskewed frame is about the size of the block, not of its upright bounding box.
      expect(s!.w).toBeGreaterThan(9 * 20 - 10);
      expect(s!.w).toBeLessThan(9 * 20 + 20);
      expect(s!.h).toBeLessThan(3 * 20 + 20);
      expect(s!.bow).toBeUndefined();
    }
  });

  it("leaves upright text alone", () => {
    const img = image(400, 300);
    block(img, 200, 150, 4, 8, 16, 0);
    expect(textSlant(img, [{ x: 40, y: 40, w: 320, h: 220 }], 16)).toBeUndefined();
  });

  it("finds the bow of a single line of glyphs set along a curve", () => {
    const img = image(460, 220);
    const n = 12, s = 16, length = 360, bow = -40; // bulges up (towards -y)
    for (let k = 0; k < n; k++) {
      const t = (2 * (k + 0.5)) / n - 1;
      const across = bow * (1 - t * t);
      const slope = (-4 * bow * t) / length;
      glyph(img, 50 + ((t + 1) * length) / 2, 140 + across, s, Math.atan(slope));
    }
    const sl = textSlant(img, [{ x: 30, y: 70, w: 400, h: 110 }], s);
    // A symmetric arc has no tilt, only a bow.
    expect(sl).toBeDefined();
    expect(sl!.angle).toBe(0);
    expect(sl!.column).toBe(false);
    expect(Math.abs(sl!.bow! - bow)).toBeLessThan(12);
    const xs: number[] = [], ys: number[] = [];
    for (let y = 70; y < 180; y++)
      for (let x = 30; x < 430; x++) if (img.data[(y * img.width + x) * 4] < 100) (xs.push(x), ys.push(y));
    const mid = (Math.min(...ys) + Math.max(...ys)) / 2;
    const found = arcBow(xs, ys, Math.min(...xs), Math.max(...xs) - Math.min(...xs), mid, s);
    expect(sl?.angle ?? 0).toBeCloseTo(0, 1);
    expect(found).toBeDefined();
    expect(Math.sign(found!)).toBe(-1);
    expect(Math.abs(found! - bow)).toBeLessThan(12);
    // A straight line of the same glyphs has no bow.
    const flat = image(460, 220);
    for (let k = 0; k < n; k++) glyph(flat, 50 + ((k + 0.5) * length) / n, 120, s, 0);
    const fx: number[] = [], fy: number[] = [];
    for (let y = 70; y < 180; y++)
      for (let x = 30; x < 430; x++) if (flat.data[(y * flat.width + x) * 4] < 100) (fx.push(x), fy.push(y));
    expect(arcBow(fx, fy, Math.min(...fx), Math.max(...fx) - Math.min(...fx), 120, s)).toBeUndefined();
  });
});

describe("renderTranslation on slanted and curved free text", () => {
  it("letters a tilted card's text at the card's angle, over the old text", () => {
    // A form on a card drawn at an angle (MN109-Akuhamu-004): upright lettering cut across it.
    const img = image(400, 300);
    block(img, 200, 150, 3, 9, 16, (12 * Math.PI) / 180);
    const box = inkBounds(img);
    const r: TextRegion = { id: "r1", kind: "free", box, members: [box], score: 1, order: 0 };
    const out = renderTranslation(ctxOver(img), { w: 400, h: 300 }, [r], { r1: tr("r1", "あいうえおかきくけこさしすせそたちつてとなにぬねのはひ", "Địa chỉ: Ma giới, quận Itabashi, phố Majin 1-2-34") }, {
      patches: { r1: { x: box.x, y: box.y, image: {}, textBoxes: [box] } },
    });
    const res = out[0];
    expect(res.status).toBe("lettered");
    expect(res.overflow).toBe(false);
    expect(Math.abs((res.angle! * 180) / Math.PI - 12)).toBeLessThan(2);
    expect(res.curved).toBeFalsy();
    // The turned lettering stays over the old text, not spread across the page.
    const near = expand(box, 12);
    const t = res.textBox!;
    expect(t.x >= near.x && t.y >= near.y && t.x + t.w <= near.x + near.w && t.y + t.h <= near.y + near.h).toBe(true);
  });

  it("letters a caption set along an arc along the same arc", () => {
    const img = image(460, 220);
    const n = 12, s = 16, length = 360, bow = -40;
    for (let k = 0; k < n; k++) {
      const t = (2 * (k + 0.5)) / n - 1;
      glyph(img, 50 + ((t + 1) * length) / 2, 140 + bow * (1 - t * t), s, Math.atan((-4 * bow * t) / length));
    }
    const box = inkBounds(img);
    const r: TextRegion = { id: "r1", kind: "free", box, members: [box], score: 1, order: 0 };
    const out = renderTranslation(ctxOver(img), { w: 460, h: 220 }, [r], { r1: tr("r1", "あいうえおかきくけこさし", "Chào mừng đến lễ hội mùa hè") }, {
      patches: { r1: { x: box.x, y: box.y, image: {}, textBoxes: [box] } },
    });
    expect(out[0].status).toBe("lettered");
    expect(out[0].curved).toBe(true);
    expect(out[0].layout!.lines).toHaveLength(1);
    expect(out[0].layout!.fontSize).toBeGreaterThanOrEqual(13);
  });

  it("letters a card line by line on its printed lines, left-aligned, in order", () => {
    // A licence-style card: three left-aligned printed rows of different lengths.
    const img = image(420, 260);
    const rows = [9, 12, 6];
    rows.forEach((n, k) => {
      for (let i = 0; i < n; i++) glyph(img, 60 + i * 22, 70 + k * 40, 16, 0);
    });
    const box = inkBounds(img);
    const r: TextRegion = { id: "r1", kind: "free", box, members: [box], score: 1, order: 0 };
    const vi = "Họ tên: Hamuru Kinsuki, sinh ngày 10 tháng 9 năm 12 Ma giới, địa chỉ quận Itabashi phố Majin 1-2-34";
    const out = renderTranslation(ctxOver(img), { w: 420, h: 260 }, [r], { r1: tr("r1", "あ".repeat(27), vi) }, {
      patches: { r1: { x: box.x, y: box.y, image: {}, textBoxes: [box] } },
    });
    const lines = out[0].layout!.lines;
    expect(out[0].status).toBe("lettered");
    expect(lines).toHaveLength(3);
    expect(lines.map((l) => l.text).join(" ")).toBe(vi);
    for (let k = 0; k < 3; k++) {
      // Starts at the printed line's left edge, sits on its row.
      // (Upright card: the frame's page origin is the area's corner.)
      expect(Math.abs(out[0].area!.x + lines[k].cx - lines[k].width / 2 - (60 - 8))).toBeLessThan(4);
      expect(Math.abs(lines[k].top + out[0].layout!.fontSize * 0.58 - (lines[0].top + out[0].layout!.fontSize * 0.58) - k * 40)).toBeLessThan(6);
    }
    // The long middle row takes the most words.
    expect(lines[1].text.split(" ").length).toBeGreaterThan(lines[2].text.split(" ").length);
    // Line breaks the model gave are kept when they match the rows.
    const given = "Họ tên: Hamuru Kinsuki\nĐịa chỉ: quận Itabashi, phố Majin 1-2-34\nCó hiệu lực";
    const out2 = renderTranslation(ctxOver(img), { w: 420, h: 260 }, [r], { r1: tr("r1", "あ".repeat(27), given) }, {
      patches: { r1: { x: box.x, y: box.y, image: {}, textBoxes: [box] } },
    });
    expect(out2[0].layout!.lines.map((l) => l.text)).toEqual(given.split("\n"));
  });

  it("keeps upright free text upright", () => {
    const img = image(400, 300);
    block(img, 200, 150, 3, 9, 16, 0);
    const box = inkBounds(img);
    const r: TextRegion = { id: "r1", kind: "free", box, members: [box], score: 1, order: 0 };
    const out = renderTranslation(ctxOver(img), { w: 400, h: 300 }, [r], { r1: tr("r1", "あいうえお", "Xin chào") }, {
      patches: { r1: { x: box.x, y: box.y, image: {}, textBoxes: [box] } },
    });
    expect(out[0].angle).toBeUndefined();
    expect(out[0].curved).toBeFalsy();
  });
});

describe("avoidAreas", () => {
  it("cuts a tilted frame back from a photo at its side and from a block below it, keeping the most room", () => {
    const a = (-18 * Math.PI) / 180;
    const card: Slant = { angle: a, cx: 300, cy: 200, w: 300, h: 190, gain: 2, column: false };
    // A photo filling the right quarter of the frame, full height.
    const c = Math.cos(a), s = Math.sin(a);
    const at = (u: number, v: number): [number, number] => [300 + u * c - v * s, 200 + u * s + v * c];
    const photo = [at(80, -95), at(150, -95), at(150, 95), at(80, 95)];
    const side = avoidAreas(card, [photo]);
    expect(side.w).toBeLessThan(240);
    expect(side.h).toBeCloseTo(190, 0);
    // A smaller tilted block over the bottom half: the frame gives up its bottom, not its width.
    const below = [at(-150, 10), at(70, 10), at(70, 120), at(-150, 120)];
    const cut = avoidAreas(card, [below]);
    expect(cut.w).toBeCloseTo(300, 0);
    expect(cut.h).toBeLessThan(110);
    expect(frameHas(cut, ...at(0, 60))).toBe(false);
    expect(frameHas(cut, ...at(0, -60))).toBe(true);
  });
});

describe("placeOnArc", () => {
  it("centres the characters on the arc and turns each along it", () => {
    const pos = placeOnArc([10, 10, 10, 10, 10], 200, -30);
    expect(pos).toHaveLength(5);
    expect(pos[2].along).toBeCloseTo(100, 0); // middle character at the middle
    expect(pos[2].across).toBeCloseTo(-30, 0);
    expect(pos[0].angle).toBeLessThan(0); // rising on the left of an arc bulging up (-y)
    expect(pos[4].angle).toBeGreaterThan(0);
    for (let i = 1; i < 5; i++) expect(pos[i].along).toBeGreaterThan(pos[i - 1].along);
  });
});
