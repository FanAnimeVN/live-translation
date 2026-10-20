import { describe, expect, it } from "vitest";
import { buildRecallParts, findGutters, parseNotesObject, PROMPT_VERSION, SYSTEM_PROMPT, type Gutter, type RGBAImage } from "../src";

/** A page painted with rectangles: [x, y, w, h, grey]. */
function page(w: number, h: number, bg: number, rects: Array<[number, number, number, number, number]>): RGBAImage {
  const data = new Uint8ClampedArray(w * h * 4).fill(bg);
  for (let i = 3; i < data.length; i += 4) data[i] = 255;
  for (const [x0, y0, rw, rh, v] of rects)
    for (let y = y0; y < y0 + rh; y++)
      for (let x = x0; x < x0 + rw; x++) {
        const i = (y * w + x) * 4;
        data[i] = data[i + 1] = data[i + 2] = v;
      }
  return { width: w, height: h, data };
}

/** A framed panel: 3 px black border around a filled interior. */
const panel = (x: number, y: number, w: number, h: number, fill: number): Array<[number, number, number, number, number]> => [
  [x, y, w, h, 0],
  [x + 3, y + 3, w - 6, h - 6, fill],
];

const key = (g: Gutter) => `${g.dir} ${g.tone} ${g.x},${g.y} ${g.w}x${g.h}`;

describe("findGutters", () => {
  it("finds margins, the gutter between panel rows and the one inside a row", () => {
    const img = page(300, 400, 255, [...panel(20, 20, 120, 160, 128), ...panel(160, 20, 120, 160, 128), ...panel(20, 200, 260, 180, 128)]);
    const gs = findGutters(img, { minThickness: 6 }).map(key);
    expect(gs).toContain("h white 0,0 300x20"); // top margin
    expect(gs).toContain("h white 0,180 300x20"); // between the rows
    expect(gs).toContain("h white 0,380 300x20"); // bottom margin
    expect(gs).toContain("v white 140,20 20x160"); // between the two panels of row 1
    expect(gs).toContain("v white 0,20 20x160"); // left margin beside row 1
  });

  it("finds black gutters and never treats a white framed panel as a gutter", () => {
    const dark = page(300, 400, 0, [[20, 20, 260, 160, 200], [20, 200, 260, 180, 200]]);
    expect(findGutters(dark, { minThickness: 6 }).map(key)).toContain("h black 0,180 300x20");
    const blank = page(300, 400, 255, [...panel(20, 20, 260, 360, 255)]);
    for (const g of findGutters(blank, { minThickness: 6 })) {
      // Only margins outside the frame: nothing inside [23, 377] × [23, 277].
      const inside = g.x >= 23 && g.x + g.w <= 277 && g.y >= 23 && g.y + g.h <= 377;
      expect(inside).toBe(false);
    }
  });

  it("tolerates scan specks but not a line crossing the band", () => {
    const specks = page(300, 200, 255, [...panel(10, 10, 280, 80, 100), ...panel(10, 110, 280, 80, 100), [50, 98, 1, 1, 0], [200, 101, 1, 1, 0]]);
    expect(findGutters(specks, { minThickness: 6 }).map(key)).toContain("h white 0,90 300x20");
    const crossed = page(300, 200, 255, [...panel(10, 10, 280, 80, 100), ...panel(10, 110, 280, 80, 100), [150, 85, 3, 30, 0]]);
    expect(findGutters(crossed, { minThickness: 6 }).some((g) => g.dir === "h" && g.y === 90)).toBe(false);
  });
});

describe("prompt v5 recall and speakers", () => {
  it("asks for an optional recall request in the notes line, and labels for people not yet named", () => {
    expect(PROMPT_VERSION).toBe("vlm-ja-vi-v5");
    expect(SYSTEM_PROMPT).toContain('"recall":{"regions"');
    expect(SYSTEM_PROMPT).toContain('"(girl, short hair)"');
  });

  it("parses recall and ps, and ignores malformed ones without losing the notes", () => {
    const n = parseNotesObject({
      type: "notes",
      names: [{ ja: "ナナ", vi: "Nana", kind: "character", evidence: "r1" }],
      recall: { regions: ["r7", " r7 ", "r9"], who: ["Nana", "unknown"], keys: ["約束", "lời hứa"] },
      ps: [{ region: "r7", card: "c1", label: "lời hứa ở lễ hội" }, { region: "", card: "c2" }],
    })!;
    expect(n.recall).toEqual({ regions: ["r7", "r9"], who: ["Nana"], keys: ["約束", "lời hứa"] });
    expect(n.ps).toEqual([{ region: "r7", card: "c1", label: "lời hứa ở lễ hội" }]);
    const bad = parseNotesObject({ type: "notes", names: [{ ja: "ナナ", vi: "Nana" }], recall: "yes", ps: { region: "r1" } })!;
    expect(bad.names).toHaveLength(1);
    expect(bad.recall).toBeUndefined();
    expect(bad.ps).toBeUndefined();
    expect(parseNotesObject({ type: "notes", recall: { regions: [] } })!.recall).toBeUndefined();
  });

  it("builds a text-only recall request with the cards and only the asked ids", () => {
    const parts = buildRecallParts({
      title: "T",
      position: { chapter: 4, page: 2 },
      lines: [
        { id: "r1", speaker: "Nana", to: "Sota", ja: "あの約束…", vi: "Lời hứa đó…", role: "dialogue" },
        { id: "r2", speaker: "unknown", to: "unknown", ja: "え？", vi: "Hả?", role: "dialogue" },
      ],
      ids: ["r1"],
      cards: "c1 (chapter 1, page 3; promise; Nana, Sota): Nana hứa với Sota",
      stableMemory: "Cast: …",
    });
    expect(parts.every((p) => p.type === "text")).toBe(true);
    const text = parts.map((p) => (p.type === "text" ? p.text : "")).join("\n");
    expect(text).toContain("c1 (chapter 1, page 3; promise; Nana, Sota)");
    expect(text).toContain("r1 [Nana→Sota] (dialogue) あの約束… => Lời hứa đó…");
    expect(text).toContain("Revise ONLY these ids: r1,");
  });
});
