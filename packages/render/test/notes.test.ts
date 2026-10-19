import { describe, expect, it } from "vitest";
import type { Gutter } from "@lt/core";
import { placeNotes } from "../src";

// Monospace stand-in: each character is 0.55 em wide.
const measure = (t: string, px: number) => t.length * px * 0.55;
const size = { w: 1000, h: 1500 };
const overlaps = (a: { x: number; y: number; w: number; h: number }, b: { x: number; y: number; w: number; h: number }) =>
  a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;

describe("placeNotes", () => {
  const text = "P/S: lời hứa ở lễ hội — chương 1, trang 3.";
  const gutters: Gutter[] = [
    { x: 0, y: 700, w: 1000, h: 30, dir: "h", tone: "white" },
    { x: 0, y: 1440, w: 1000, h: 60, dir: "h", tone: "white" },
  ];

  it("letters the note inside the nearest gutter with room, centred on its balloon", () => {
    const anchor = { x: 600, y: 560, w: 200, h: 120 };
    const [p] = placeNotes([{ id: "r7", text, anchor }], gutters, measure, size);
    expect(p.mode).toBe("inline");
    expect(p.box.y).toBeGreaterThanOrEqual(700);
    expect(p.box.y + p.box.h).toBeLessThanOrEqual(730);
    expect(Math.abs(p.box.x + p.box.w / 2 - 700)).toBeLessThan(2);
    expect(p.lines.join(" ")).toBe(text);
  });

  it("falls back to a dot when no gutter is near or has room, and never covers a region", () => {
    const anchor = { x: 100, y: 100, w: 200, h: 120 };
    const [far] = placeNotes([{ id: "r1", text, anchor }], gutters, measure, size);
    expect(far.mode).toBe("dot"); // the nearest gutter is 480 px away
    const balloon = { x: 600, y: 690, w: 200, h: 60 }; // a balloon sitting across the gutter
    const [blocked] = placeNotes([{ id: "r2", text, anchor: { x: 600, y: 560, w: 200, h: 120 } }], gutters.slice(0, 1), measure, size, { avoid: [balloon] });
    expect(blocked.mode).toBe("dot");
    const thin: Gutter[] = [{ x: 0, y: 700, w: 1000, h: 8, dir: "h", tone: "white" }];
    expect(placeNotes([{ id: "r3", text, anchor: { x: 600, y: 560, w: 200, h: 120 } }], thin, measure, size)[0].mode).toBe("dot");
  });

  it("two notes near the same gutter do not overlap", () => {
    const a = placeNotes(
      [
        { id: "r1", text, anchor: { x: 500, y: 560, w: 200, h: 120 } },
        { id: "r2", text, anchor: { x: 520, y: 560, w: 200, h: 120 } },
      ],
      gutters,
      measure,
      size,
    );
    const inline = a.filter((p) => p.mode === "inline");
    if (inline.length === 2) expect(overlaps(inline[0].box, inline[1].box)).toBe(false);
    expect(a).toHaveLength(2);
  });
});
