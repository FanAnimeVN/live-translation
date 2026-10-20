import { describe, expect, it } from "vitest";
import {
  applyRegionRules,
  buildRegions,
  cer,
  chrfScore,
  chrfStats,
  fromPermille,
  parseNotesObject,
  emptyMemory,
  fixHonorificStacking,
  JsonObjectStream,
  layoutText,
  memoryContext,
  mergePage,
  parseRegionObject,
  setEntityStatus,
  xyCutOrder,
  type Detection,
} from "../src";

describe("JsonObjectStream", () => {
  it("extracts objects split across arbitrary chunks, fences and commentary", () => {
    const got: unknown[] = [];
    const s = new JsonObjectStream((v) => got.push(v));
    const text = '```json\n{"id":"r1","vi":"Chào {bạn}"}\n{"id":"r2","vi":"Nói \\"không\\" đi"}\nthanks\n{"type":"notes","names":[]}\n```';
    for (let i = 0; i < text.length; i += 5) s.push(text.slice(i, i + 5));
    expect(got).toEqual([{ id: "r1", vi: "Chào {bạn}" }, { id: "r2", vi: 'Nói "không" đi' }, { type: "notes", names: [] }]);
  });

  it("reports a truncated trailing object as pending, not as a result", () => {
    const got: unknown[] = [];
    const s = new JsonObjectStream((v) => got.push(v));
    s.push('{"id":"r1","vi":"a"}\n{"id":"r2","vi":"cắt giữa');
    expect(got).toHaveLength(1);
    expect(s.pending).toContain('"r2"');
  });
});

describe("honorific no-stack rule", () => {
  it("removes a Vietnamese kinship title stacked on a retained sibling vocative", () => {
    expect(fixHonorificStacking("Chị nee-chan, đợi em!").text).toBe("Nee-chan, đợi em!");
    expect(fixHonorificStacking("chị gái nee-chan").text).toBe("nee-chan");
    expect(fixHonorificStacking("Anh trai onii-chan!").text).toBe("Onii-chan!");
    expect(fixHonorificStacking("Em nhớ anh onii-chan lắm").text).toBe("Em nhớ onii-chan lắm");
  });

  it("keeps legitimate pronouns and narrative kinship", () => {
    expect(fixHonorificStacking("Em nhớ anh, onii-chan.").text).toBe("Em nhớ anh, onii-chan.");
    expect(fixHonorificStacking("Chị gái tôi là bác sĩ.").text).toBe("Chị gái tôi là bác sĩ.");
    expect(fixHonorificStacking("Onii-chan, anh đi đâu thế?").text).toBe("Onii-chan, anh đi đâu thế?");
  });

  it("is applied when parsing model output", () => {
    const t = parseRegionObject({ id: "r1", ja: "お姉ちゃん！", vi: "Chị nee-chan!", role: "dialogue" }, new Set(["r1"]), 0);
    expect(t?.vi).toBe("Nee-chan!");
    expect(t?.fixes).toEqual(["honorific-no-stack"]);
  });

  it("letters a scream in a speech bubble instead of keeping it as a sound effect", () => {
    const t = parseRegionObject({ id: "r2", ja: "ギャ～", vi: "Áaa~", role: "sfx" }, new Set(["r2"]), 0)!;
    expect(applyRegionRules(t, { kind: "bubble" })).toMatchObject({ role: "dialogue", fixes: ["bubble-not-sfx"] });
    expect(applyRegionRules(t, { kind: "free" }).role).toBe("sfx");
  });

  it("keeps the role and a valid box for text found outside every region", () => {
    const n = parseNotesObject({
      type: "notes",
      missed: [
        { ja: "ナナ", vi: "Nana", role: "sign", box: [340, 790, 380, 810] },
        { ja: "トラ", vi: "Tora", role: "label?", box: [500, 500, 400, 600] },
      ],
    })!;
    expect(n.missed[0]).toMatchObject({ role: "sign", box: [340, 790, 380, 810] });
    expect(n.missed[1].role).toBeUndefined();
    expect(n.missed[1].box).toBeUndefined();
    expect(fromPermille([500, 250, 750, 500], 800, 1200)).toEqual({ x: 400, y: 300, w: 200, h: 300 });
  });

  it("rejects unknown ids and keeps unknown speakers unknown", () => {
    expect(parseRegionObject({ id: "r9", vi: "x" }, new Set(["r1"]), 0)).toBeNull();
    const t = parseRegionObject({ id: "r1", ja: "誰？", vi: "Ai?", speaker: "", to: "N/A" }, new Set(["r1"]), 0);
    expect(t?.speaker).toBe("unknown");
    expect(t?.to).toBe("unknown");
  });
});

describe("reading order", () => {
  it("reads rows top to bottom and right to left inside a row", () => {
    const boxes = [
      { x: 0, y: 0, w: 10, h: 10 }, // top-left
      { x: 50, y: 0, w: 10, h: 10 }, // top-right
      { x: 50, y: 50, w: 10, h: 10 }, // bottom-right
    ];
    expect(xyCutOrder(boxes)).toEqual([1, 0, 2]);
  });
});

describe("buildRegions", () => {
  it("merges duplicate text boxes and attaches the containing bubble", () => {
    const dets: Detection[] = [
      { cls: "bubble", box: { x: 100, y: 100, w: 100, h: 160 }, score: 0.9 },
      { cls: "text_bubble", box: { x: 130, y: 120, w: 40, h: 120 }, score: 0.8 },
      { cls: "text_free", box: { x: 132, y: 122, w: 38, h: 115 }, score: 0.5 },
      { cls: "text_free", box: { x: 400, y: 50, w: 30, h: 90 }, score: 0.7 },
    ];
    const regions = buildRegions(dets);
    expect(regions).toHaveLength(2);
    const inBubble = regions.find((r) => r.bubble);
    expect(inBubble?.kind).toBe("bubble");
    expect(regions.map((r) => r.id)).toEqual(["r1", "r2"]);
    // the free text at x=400 is further right, so it is read first
    expect(regions[0].box.x).toBe(400);
  });

  const opts = { minScore: 0.3, minScoreInBubble: 0.1, lonelyBubble: 0.5 };

  it("keeps faint text that a confident bubble vouches for, not faint text on its own", () => {
    const dets: Detection[] = [
      { cls: "bubble", box: { x: 86, y: 852, w: 72, h: 89 }, score: 0.56 },
      { cls: "text_bubble", box: { x: 94, y: 862, w: 43, h: 62 }, score: 0.15 },
      { cls: "text_free", box: { x: 400, y: 50, w: 30, h: 90 }, score: 0.15 },
    ];
    const regions = buildRegions(dets, opts);
    expect(regions).toHaveLength(1);
    expect(regions[0]).toMatchObject({ kind: "bubble", box: { x: 94, y: 862 } });
  });

  it("drops a text box that repeats the whole balloon when a tighter one exists", () => {
    const bubble = { x: 340, y: 24, w: 114, h: 208 };
    const regions = buildRegions(
      [
        { cls: "bubble", box: bubble, score: 0.9 },
        { cls: "text_bubble", box: { ...bubble }, score: 0.4 },
        { cls: "text_bubble", box: { x: 350, y: 49, w: 70, h: 166 }, score: 0.9 },
      ],
      opts,
    );
    expect(regions).toHaveLength(1);
    expect(regions[0].members).toEqual([{ x: 350, y: 49, w: 70, h: 166 }]);
    expect(regions[0].box).toEqual({ x: 350, y: 49, w: 70, h: 166 });
  });

  it("turns a confident bubble with no text box into a region for the reader to check", () => {
    const regions = buildRegions([{ cls: "bubble", box: { x: 0, y: 0, w: 100, h: 100 }, score: 0.8 }], opts);
    expect(regions).toHaveLength(1);
    expect(regions[0].kind).toBe("bubble");
    expect(regions[0].box.x).toBeCloseTo(18);
    expect(buildRegions([{ cls: "bubble", box: { x: 0, y: 0, w: 100, h: 100 }, score: 0.4 }], opts)).toHaveLength(0);
  });
});

describe("layoutText", () => {
  const measure = (t: string, size: number) => t.length * size * 0.5;
  it("breaks a long hyphenated name after its hyphen instead of shrinking it to the minimum", () => {
    // AppareKappore-009 r3: one word, a name with a stretched honorific, in a tall narrow balloon.
    const area = { x: 0, y: 0, w: 60, h: 160, shape: "rect" as const };
    const l = layoutText("Moriguo-kuuun!", area, measure, { maxSize: 24, minSize: 8 });
    expect(l.overflow).toBe(false);
    expect(l.lines.map((x) => x.text)).toEqual(["Moriguo-", "kuuun!"]);
    expect(l.fontSize).toBeGreaterThanOrEqual(12);
    // A word that fits stays whole.
    expect(layoutText("Nana-chan", { x: 0, y: 0, w: 200, h: 60, shape: "rect" }, measure, { maxSize: 24 }).lines).toHaveLength(1);
  });

  it("fits text inside an ellipse and centers the lines", () => {
    const area = { x: 0, y: 0, w: 120, h: 120, shape: "ellipse" as const };
    const l = layoutText("Hôm nay cũng được một mẻ lớn đấy!", area, measure, { maxSize: 30 });
    expect(l.overflow).toBe(false);
    for (const line of l.lines) expect(measure(line.text, l.fontSize)).toBeLessThanOrEqual(120);
    const top = l.lines[0].top;
    const bottom = l.lines.at(-1)!.top + l.lineHeight;
    expect(Math.abs(top - (120 - bottom))).toBeLessThan(1);
  });

  it("reports overflow honestly instead of cutting text", () => {
    const area = { x: 0, y: 0, w: 30, h: 12, shape: "rect" as const };
    const l = layoutText("một câu rất dài không thể nào vừa", area, measure, { minSize: 9 });
    expect(l.overflow).toBe(true);
    expect(l.lines.join(" ")).not.toBe("");
    expect(l.lines.map((x) => x.text).join(" ")).toBe("một câu rất dài không thể nào vừa");
  });
});

describe("story memory", () => {
  const notes = (ja: string, vi: string) => ({ names: [{ ja, vi, kind: "character" as const, evidence: "r1" }], address: [], missed: [] });

  it("never exposes facts learned after the reading position", () => {
    let mem = emptyMemory("s", "S");
    mem = mergePage(mem, "p1", { chapter: 1, page: 1 }, notes("ナナ", "Nana"), []).memory;
    mem = mergePage(mem, "p9", { chapter: 3, page: 2 }, notes("黒幕", "Kẻ chủ mưu"), []).memory;
    const early = memoryContext(mem, { chapter: 2, page: 1 });
    expect(early).toContain("Nana");
    expect(early).not.toContain("Kẻ chủ mưu");
    expect(memoryContext(mem, { chapter: 3, page: 2 })).toContain("Kẻ chủ mưu");
  });

  it("keeps a reader-locked rendering when the model proposes another", () => {
    let mem = emptyMemory("s", "S");
    mem = mergePage(mem, "p1", { chapter: 1, page: 1 }, notes("ナナ", "Nana"), []).memory;
    mem = setEntityStatus(mem, "ナナ", "locked", "Nana-chan");
    const r = mergePage(mem, "p2", { chapter: 1, page: 2 }, notes("ナナ", "Nanà"), []);
    expect(r.proposals).toHaveLength(0);
    expect(r.memory.entities[0].vi).toBe("Nana-chan");
    expect(r.memory.entities[0].status).toBe("locked");
    expect(r.memory.entities[0].evidence).toHaveLength(2);
  });
});

describe("chrF", () => {
  it("scores an identical translation 100 and an unrelated one near 0, ignoring spaces and case", () => {
    expect(chrfScore([chrfStats("Tớ là Nana!", "tớ là  Nana!")])).toBeCloseTo(100);
    expect(chrfScore([chrfStats("xyz", "Tớ là Nana!")])).toBeLessThan(5);
    const close = chrfScore([chrfStats("Tớ tên là Nana!", "Tớ là Nana!")]);
    expect(close).toBeGreaterThan(60);
    expect(close).toBeLessThan(100);
  });
});

describe("cer", () => {
  it("normalizes width and whitespace before comparing", () => {
    expect(cer("あたしはナナ！！ ５さい！", "あたしはナナ!!5さい!").rate).toBe(0);
    expect(cer("さっそく", "ぎっそく").edits).toBe(1);
  });
});
