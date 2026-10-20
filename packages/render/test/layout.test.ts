import { describe, expect, it } from "vitest";
import { intersect, type Box, type RegionTranslation, type RGBAImage, type TextRegion } from "@lt/core";
import { renderTranslation, type Ctx2D, type PatchImage, type RegionRender } from "../src";

const size = { w: 400, h: 300 };

/**
 * Grey artwork with white paper inside `paper`; drawing is a no-op and text is a monospace
 * stand-in (0.55 em per character).
 */
function paperCtx(paper: Box = { x: 0, y: 0, w: size.w, h: size.h }): Ctx2D {
  const img: RGBAImage = { width: size.w, height: size.h, data: new Uint8ClampedArray(size.w * size.h * 4).fill(255) };
  for (let y = 0; y < size.h; y++) {
    for (let x = 0; x < size.w; x++) {
      if (x < paper.x || y < paper.y || x >= paper.x + paper.w || y >= paper.y + paper.h) img.data.fill(110, (y * size.w + x) * 4, (y * size.w + x) * 4 + 3);
    }
  }
  const ctx = {
    font: "",
    fillStyle: "",
    strokeStyle: "",
    lineWidth: 1,
    lineJoin: "",
    textAlign: "",
    textBaseline: "",
    globalAlpha: 1,
    measureText: (t: string) => ({ width: t.length * Number(/(\d+)px/.exec(ctx.font)?.[1] ?? 10) * 0.55 }),
    getImageData: () => img,
  };
  const noop = () => {};
  for (const k of ["fillText", "strokeText", "fillRect", "strokeRect", "putImageData", "save", "restore", "translate", "rotate", "drawImage"]) {
    (ctx as Record<string, unknown>)[k] = noop;
  }
  return ctx as unknown as Ctx2D;
}

const region = (id: string, box: Box, bubble?: Box): TextRegion => ({ id, kind: bubble ? "bubble" : "free", box, members: [box], bubble, score: 1, order: 0 });
const tr = (id: string, ja: string, vi: string): RegionTranslation => ({ id, ja, vi, role: "dialogue", speaker: "", to: "", style: [], seq: 0, fixes: [] });
// Every region sits on artwork and already has its reconstructed patch.
const patch = (r: TextRegion, textExtent?: Box): PatchImage => ({ x: r.box.x, y: r.box.y, image: {}, textBoxes: r.members, textExtent });

function expectNoOverlap(out: RegionRender[]): void {
  const lettered = out.filter((r) => r.status === "lettered");
  for (const a of lettered) {
    expect(a.textBox).toBeDefined();
    for (const b of lettered) if (a !== b) expect(intersect(a.textBox!, b.textBox!), `${a.id} touches ${b.id}`).toBeNull();
  }
}

describe("renderTranslation layout", () => {
  it("two captions growing into the same gap do not overlap, also when one starts from a tight glyph extent", () => {
    // Two vertical columns 20 px apart on a strip of paper between artwork (MN109-02 r1/r2):
    // each may grow into the gap up to the other's box, so both claim it.
    const a = region("r1", { x: 220, y: 50, w: 80, h: 200 });
    const b = region("r2", { x: 120, y: 50, w: 80, h: 200 });
    const translations = {
      r1: tr("r1", "あいうえおかきくけこさし", "Tớ là Nana! 5 tuổi!"),
      r2: tr("r2", "あいうえおかきくけこさしす", "Chuyên gia săn thằn lằn!"),
    };
    // r2's glyphs sat in the middle of its box (seeded); r1's filled its box (not seeded).
    const patches = { r1: patch(a), r2: patch(b, { x: 134, y: 62, w: 52, h: 176 }) };
    const out = renderTranslation(paperCtx({ x: 115, y: 40, w: 190, h: 220 }), size, [a, b], translations, { patches });
    expect(out.map((r) => r.status)).toEqual(["lettered", "lettered"]);
    expectNoOverlap(out);
    for (const r of out) expect(r.overflow).toBe(false);
  });

  it("a caption whose box reaches under a balloon keeps clear of the balloon's lettering", () => {
    // A thought caption tucked under the corner of a balloon, art on its right (MN109-05 r7/r8).
    const balloon = region("r1", { x: 77, y: 37, w: 65, h: 170 }, { x: 60, y: 29, w: 104, h: 188 });
    const caption = region("r2", { x: 132, y: 180, w: 49, h: 80 });
    const translations = {
      r1: tr("r1", "あいうえおかきくけこさしすせそ", "Lại sinh sôi nảy nở nữa mất!"),
      r2: tr("r2", "あいうえおかきくけ", "Hự… sẽ thế nào đây? Sẽ thế nào đây?"),
    };
    const patches = { r1: patch(balloon), r2: patch(caption) };
    const out = renderTranslation(paperCtx({ x: 0, y: 0, w: 185, h: size.h }), size, [balloon, caption], translations, { patches });
    expect(out.map((r) => r.status)).toEqual(["lettered", "lettered"]);
    expectNoOverlap(out);
    // The balloon keeps its own layout; the caption moved, it was not dropped.
    const cap = out.find((r) => r.id === "r2")!;
    expect(cap.layout!.lines.length).toBeGreaterThan(0);
    expect(intersect(cap.textBox!, caption.box)).not.toBeNull();
  });

  it("a long caption down a narrow margin column is lettered along the column, a short one stays upright", () => {
    // A promotional caption running down the page margin (MN109-02 r11): a word per line would
    // take a dozen lines; turned along the column it takes one or two, inside the old column.
    const margin = region("r1", { x: 6, y: 10, w: 40, h: 280 });
    const short = region("r2", { x: 300, y: 40, w: 30, h: 110 });
    const translations = {
      r1: tr("r1", "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめも", "Truyện mới về mèo của tác giả yêu mèo bắt đầu từ số này"),
      r2: tr("r2", "あいうえお", "Ồ?"),
    };
    const patches = { r1: patch(margin), r2: patch(short) };
    const out = renderTranslation(paperCtx(), size, [margin, short], translations, { patches });
    const col = out.find((r) => r.id === "r1")!;
    expect(col.status).toBe("lettered");
    expect(col.rotated).toBe(true);
    expect(col.overflow).toBe(false);
    expect(col.layout!.lines.length).toBeLessThanOrEqual(3);
    // The turned text stays inside the column the Japanese occupied.
    expect(col.textBox!.x).toBeGreaterThanOrEqual(margin.box.x - 1);
    expect(col.textBox!.x + col.textBox!.w).toBeLessThanOrEqual(margin.box.x + margin.box.w + 1);
    expect(out.find((r) => r.id === "r2")!.rotated).toBeFalsy();
  });
});
