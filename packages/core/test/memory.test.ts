import { describe, expect, it } from "vitest";
import {
  applyDigests,
  applyMemoryUpdate,
  backgroundInput,
  emptyMemory,
  estimateTokens,
  makeDigest,
  makeOverview,
  MEMORY_BUDGET,
  mergePage,
  setEntityStatus,
  stableContext,
  volatileContext,
  type PageNotes,
  type RegionTranslation,
  type SeriesMemory,
} from "../src";

const pos = (chapter: number, page: number) => ({ chapter, page });
const notes = (over: Partial<PageNotes> = {}): PageNotes => ({ names: [], address: [], missed: [], ...over });
const line = (id: string, ja: string, vi: string, speaker = "unknown", to = "unknown"): RegionTranslation => ({
  id,
  ja,
  vi,
  role: "dialogue",
  speaker,
  to,
  style: [],
  seq: Number(id.slice(1)),
  fixes: [],
});

describe("context v2", () => {
  it("cold start: a series note from the first page becomes the profile once", () => {
    let mem = emptyMemory("s", "S");
    mem = mergePage(mem, "p1", pos(1, 1), notes({ series: { genres: ["slice of life"], tone: "warm comedy" } }), []).memory;
    mem = mergePage(mem, "p2", pos(1, 2), notes({ series: { genres: ["horror"] } }), []).memory;
    expect(mem.profile?.genres).toEqual(["slice of life"]);
    expect(stableContext(mem, pos(1, 2))).toContain("warm comedy");
  });

  it("metadata enriches a character only once it appears in the story", () => {
    let mem: SeriesMemory = {
      ...emptyMemory("s", "S"),
      metadata: {
        source: "anilist",
        id: 1,
        title: "T",
        fetchedAt: "",
        characters: [
          { native: "小岩井四葉", full: "Yotsuba Koiwai", alternative: [], gender: "Female", role: "MAIN", relations: ["adopted daughter of Yousuke"] },
          { native: "綾瀬風香", full: "Fuuka Ayase", alternative: [], gender: "Female", role: "MAIN" },
        ],
      },
    };
    expect(stableContext(mem, pos(1, 1))).not.toContain("Fuuka");
    mem = mergePage(mem, "p1", pos(1, 1), notes({ names: [{ ja: "四葉", vi: "Yotsuba", kind: "character", evidence: "r1" }] }), []).memory;
    const card = mem.entities.find((e) => e.ja === "四葉")!;
    expect(card.gender).toBe("female");
    expect(card.officialName).toBe("Yotsuba Koiwai");
    const ctx = stableContext(mem, pos(1, 1));
    expect(ctx).toContain("adopted daughter");
    expect(ctx).not.toContain("Fuuka"); // not seen yet: no spoiler of later characters
  });

  it("never shows a summary written from later pages when reading earlier ones", () => {
    let mem = emptyMemory("s", "S");
    mem = mergePage(mem, "p9", pos(3, 9), notes(), [line("r1", "犯人はお前だ", "Hung thủ là cậu!")]).memory;
    const ch2 = makeDigest("chapter", [2, 2], "Hung thủ đã lộ diện.", [{ text: "x", pos: pos(2, 9), evidence: [] }], "m");
    mem = applyDigests(mem, [ch2], makeOverview("Hung thủ đã lộ diện.", [ch2], "m"));
    expect(volatileContext(mem, pos(3, 9))).toContain("Hung thủ đã lộ diện");
    expect(volatileContext(mem, pos(2, 1))).not.toContain("Hung thủ");
  });

  it("background updates fill gaps but never override reader locks", () => {
    let mem = emptyMemory("s", "S");
    mem = mergePage(mem, "p1", pos(1, 1), notes({ names: [{ ja: "ナナ", vi: "Nana", kind: "character", evidence: "r1" }] }), [line("r1", "あたしはナナ", "Tớ là Nana", "Nana")]).memory;
    mem = setEntityStatus(mem, "ナナ", "locked", "Nana-chan");
    mem = applyMemoryUpdate(mem, { characters: [{ name: "Nana-chan", ja: "ナナ", gender: "male", relations: ["x"] }] }, pos(1, 1), "m");
    const nana = mem.entities[0];
    expect(nana.vi).toBe("Nana-chan");
    expect(nana.gender).toBeUndefined();
  });

  it("address rules from a summary need evidence from pages already read", () => {
    let mem = emptyMemory("s", "S");
    mem = mergePage(mem, "p1", pos(1, 1), notes(), [line("r2", "ご主人さま！", "Chủ nhân!", "Nana", "Owner")]).memory;
    mem = applyMemoryUpdate(
      mem,
      {
        address: [
          { from: "Nana", to: "Owner", self_vi: "tớ", address_vi: "chủ nhân", evidence: ["p1:r2"] },
          { from: "Owner", to: "Nana", self_vi: "tao", address_vi: "mày", evidence: [] },
        ],
      },
      pos(1, 1),
      "m",
    );
    expect(mem.address).toHaveLength(1);
    expect(mem.address[0]).toMatchObject({ from: "Nana", to: "Owner", addressVi: "chủ nhân", source: "summary" });
  });

  it("archives every summary and shows the story as it stood at the reading position", () => {
    let mem = emptyMemory("s", "S");
    mem = mergePage(mem, "p3", pos(1, 3), notes(), [line("r1", "a", "a")]).memory;
    mem = applyMemoryUpdate(mem, { segment: "Họ gặp nhau." }, pos(1, 3), "m1");
    mem = mergePage(mem, "p5", pos(2, 5), notes(), [line("r1", "b", "b")]).memory;
    mem = applyMemoryUpdate(mem, { segment: "Bí mật lộ ra." }, pos(2, 5), "m2");
    expect(mem.archive).toHaveLength(2);
    expect(mem.archive![0]).toMatchObject({ from: pos(1, 3), upTo: pos(1, 3), segment: "Họ gặp nhau.", model: "m1" });
    expect(mem.archive![0].story).toBeUndefined(); // no rolling story any more
    expect(volatileContext(mem, pos(1, 9))).toContain("Họ gặp nhau."); // re-reading chapter 1
    expect(volatileContext(mem, pos(1, 9))).not.toContain("Bí mật");
    expect(volatileContext(mem, pos(2, 6))).toContain("Bí mật lộ ra.");
    expect(volatileContext(mem, pos(2, 6))).toContain("Họ gặp nhau."); // recent developments
  });

  it("keeps a long series within the token budget, active characters first", () => {
    let mem = emptyMemory("s", "S");
    const names = Array.from({ length: 300 }, (_, i) => ({ ja: `キャラ${i}`, vi: `Nhân vật ${i}`, kind: "character" as const, evidence: "r1" }));
    mem = mergePage(mem, "p1", pos(1, 1), notes({ names }), []).memory;
    mem = {
      ...mem,
      address: names.slice(0, 200).map((n, i) => ({ from: n.vi, to: names[(i + 1) % 200].vi, selfVi: "tôi", addressVi: "cậu", status: "auto" as const, knownFrom: pos(1, 1), evidence: [], count: 1 })),
      archive: Array.from({ length: 1000 }, (_, i) => ({ from: pos(i + 1, 1), upTo: pos(i + 1, 20), segment: `Sự kiện chương ${i + 1} `.repeat(6), story: "Câu chuyện dài. ".repeat(40), events: [], model: "m", at: "" })),
    };
    mem = mergePage(mem, "p9", pos(1000, 21), notes(), [line("r1", "やあ", "Chào", "Nhân vật 299", "Nhân vật 298")]).memory;
    const stable = stableContext(mem, pos(1000, 21));
    const recent = volatileContext(mem, pos(1000, 21));
    expect(estimateTokens(stable)).toBeLessThanOrEqual(MEMORY_BUDGET.stable);
    expect(estimateTokens(recent)).toBeLessThanOrEqual(MEMORY_BUDGET.volatile);
    expect(stable).toContain("Nhân vật 299"); // the speaker on the latest page made it in
    expect(stable).toContain("older entries not shown");
    expect(JSON.stringify(backgroundInput(mem)).length).toBeLessThan(6000); // background input does not grow with the series
  });

  it("keeps dialogue read while an update was running", () => {
    let mem = emptyMemory("s", "S");
    mem = mergePage(mem, "p1", pos(1, 1), notes(), [line("r1", "a", "a")]).memory;
    const late = { pageId: "p2", regionId: "r1", speaker: "unknown", ja: "b", vi: "b", pos: pos(1, 2) };
    mem = applyMemoryUpdate(mem, { story_so_far: "x" }, pos(1, 1), "m", [late]);
    expect(mem.pending).toEqual([late]);
  });
});
