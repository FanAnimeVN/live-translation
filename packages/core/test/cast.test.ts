import { describe, expect, it } from "vitest";
import { answerCast, castQuestions, emptyMemory, mergePage, presetLabel, presetShort, stableContext, type PageNotes, type RegionTranslation, type SeriesMemory } from "../src";

// Made-up cast (not from any manga): Kenta and Yui.
const pos = (page: number) => ({ chapter: 1, page });
const notes = (over: Partial<PageNotes> = {}): PageNotes => ({ names: [], address: [], missed: [], ...over });
const line = (id: string, speaker: string, to: string): RegionTranslation => ({ id, ja: "…", vi: "…", role: "dialogue", speaker, to, style: [], seq: Number(id.slice(1)), fixes: [] });
const names = [
  { ja: "健太", vi: "Kenta", kind: "character" as const, evidence: "r1" },
  { ja: "結衣", vi: "Yui", kind: "character" as const, evidence: "r2" },
];

function read(pages: Array<{ lines: RegionTranslation[]; address?: PageNotes["address"] }>): SeriesMemory {
  let mem = emptyMemory("s", "S");
  pages.forEach((p, i) => {
    mem = mergePage(mem, `p${i + 1}`, pos(i + 1), notes({ names, address: p.address ?? [] }), p.lines).memory;
  });
  return mem;
}

describe("cast questions", () => {
  it("asks who talks a lot but has no gender, and which pair two people use, then never again", () => {
    const mem = read([
      { lines: [line("r1", "Kenta", "Yui"), line("r2", "Yui", "Kenta")], address: [{ from: "Kenta", to: "Yui", self_vi: "tớ", address_vi: "cậu", evidence: "r1" }] },
      { lines: [line("r1", "Kenta", "Yui"), line("r2", "Kenta", "unknown")] },
    ]);
    const qs = castQuestions(mem, pos(2), 3);
    expect(qs.map((q) => q.id)).toEqual(["pair:健太|結衣", "gender:健太", "gender:結衣"]);
    expect(qs[0]).toMatchObject({ kind: "pair", guess: "to-cau", lines: 3 });

    let next = answerCast(mem, qs[0], "anh-em", pos(2), "t");
    next = answerCast(next, qs[1], "male", pos(2), "t");
    expect(next.address.find((a) => a.from === "Kenta" && a.to === "Yui")).toMatchObject({ selfVi: "anh", addressVi: "em", status: "locked", source: "reader" });
    expect(next.address.find((a) => a.from === "Kenta" && a.to === "Yui")?.history?.[0]).toMatchObject({ selfVi: "tớ", addressVi: "cậu", status: "auto" });
    expect(next.address.find((a) => a.from === "Yui" && a.to === "Kenta")).toMatchObject({ selfVi: "em", addressVi: "anh", status: "locked" });
    expect(next.entities.find((e) => e.ja === "健太")).toMatchObject({ gender: "male", genderBy: "reader" });
    expect(castQuestions(next, pos(3), 3).map((q) => q.id)).toEqual(["gender:結衣"]);
    expect(stableContext(next, pos(3))).toContain("Kenta → Yui: self \"anh\", addresses as \"em\" {locked}");
    expect(presetLabel("anh-em", "Kenta", "Yui")).toBe("Kenta xưng anh, gọi Yui là em · Yui xưng em, gọi Kenta là anh");
    expect([presetShort("anh-em", "Kenta", "Yui"), presetShort("to-cau", "Kenta", "Yui")]).toEqual(["Kenta là anh, Yui là em", "Ngang hàng: tớ–cậu"]);
  });

  it("does not ask what two pages already agree on, and marks a contradicted rule as ambiguous", () => {
    const tc = (from: string, to: string) => ({ from, to, self_vi: "tớ", address_vi: "cậu", evidence: "r1" });
    const agreed = read([
      { lines: [line("r1", "Kenta", "Yui"), line("r2", "Yui", "Kenta")], address: [tc("Kenta", "Yui"), tc("Yui", "Kenta")] },
      { lines: [line("r1", "Kenta", "Yui")], address: [tc("Kenta", "Yui"), tc("Yui", "Kenta")] },
    ]);
    expect(castQuestions(agreed, pos(2), 3, { gender: 99, pair: 2 })).toEqual([]);
    expect(stableContext(agreed, pos(2))).toContain("{auto, seen 2×}");

    const torn = read([
      { lines: [line("r1", "Kenta", "Yui")], address: [tc("Kenta", "Yui")] },
      { lines: [line("r1", "Kenta", "Yui")], address: [{ from: "Kenta", to: "Yui", self_vi: "anh", address_vi: "em", evidence: "r1" }] },
    ]);
    expect(stableContext(torn, pos(2))).toContain("ambiguous: contradicted 1×");
    expect(castQuestions(torn, pos(2), 3, { gender: 99, pair: 2 }).map((q) => q.id)).toEqual(["pair:健太|結衣"]);
  });

  it("names a label: the model only suggests, the reader's tap rewrites the lines and wins", () => {
    const boy = "(boy, glasses)";
    let mem = emptyMemory("s", "S");
    mem = mergePage(mem, "p1", pos(1), notes(), [line("r1", boy, "(girl, bob cut)"), line("r2", "(girl, bob cut)", boy)]).memory;
    expect(mem.recent.map((l) => l.speaker)).toEqual([boy, "(girl, bob cut)"]);
    // Page 2 names him and says which label he had: a suggestion, shown as the card's guess; nothing is rewritten yet.
    mem = mergePage(mem, "p2", pos(2), notes({ names: [{ ...names[0], was: boy }] }), [line("r1", boy, "unknown")]).memory;
    expect(mem.recent.map((l) => l.speaker)).toEqual([boy, "(girl, bob cut)", boy]);
    expect(stableContext(mem, pos(3))).not.toContain("aka");
    const guessed = castQuestions(mem, pos(2), 3, { who: 2 }).find((q) => q.id === `who:${boy}`)!;
    expect(guessed.guess).toBe("Kenta");
    mem = answerCast(mem, guessed, "name:健太", pos(2));
    expect(mem.recent.map((l) => l.speaker)).toEqual(["Kenta", "(girl, bob cut)", "Kenta"]);
    expect(mem.recent[1].to).toBe("Kenta");
    expect(stableContext(mem, pos(3))).toContain("aka (boy, glasses)");

    // The reader names the girl's label with one tap; the model cannot move a reader's label elsewhere.
    mem = mergePage(mem, "p3", pos(3), notes({ names: [names[1]] }), [line("r1", "(girl, bob cut)", "Kenta"), line("r2", "(girl, bob cut)", "Kenta")]).memory;
    const who = castQuestions(mem, pos(3), 3).find((q) => q.kind === "who")!;
    expect(who).toMatchObject({ id: "who:(girl, bob cut)", lines: 4 });
    mem = answerCast(mem, who, "name:結衣", pos(3));
    expect(mem.recent.filter((l) => l.speaker === "Yui")).toHaveLength(3);
    mem = mergePage(mem, "p4", pos(4), notes({ names: [{ ...names[0], was: "(girl, bob cut)" }] }), [line("r1", "(girl, bob cut)", "Kenta")]).memory;
    expect(mem.recent.at(-1)?.speaker).toBe("Yui");
    expect(castQuestions(mem, pos(4), 3).some((q) => q.kind === "who")).toBe(false);
  });

  it("lets the reader set a pair between two labels, and type a name for one", () => {
    const [a, b] = ["(old man, beard)", "(boy, cap)"];
    let mem = emptyMemory("s", "S");
    mem = mergePage(mem, "p1", pos(1), notes(), [line("r1", a, b), line("r2", b, a), line("r3", a, b), line("r4", b, a)]).memory;
    const qs = castQuestions(mem, pos(1), 4);
    expect(qs.map((q) => q.kind).sort()).toEqual(["pair", "who", "who"]);
    mem = answerCast(mem, qs.find((q) => q.kind === "pair")!, qs.find((q) => q.kind === "pair")!.who[0].vi === a ? "bo-con" : "con-bo", pos(1));
    expect(mem.address.find((r) => r.from === a)).toMatchObject({ to: b, selfVi: "bố", addressVi: "con", status: "locked" });
    mem = answerCast(mem, qs.find((q) => q.id === `who:${a}`)!, "new:Ông Tanaka", pos(1));
    expect(mem.entities.find((e) => e.vi === "Ông Tanaka")).toMatchObject({ status: "locked", source: "reader", aliases: [{ label: a, by: "reader" }] });
    expect(mem.address.find((r) => r.from === "Ông Tanaka")).toMatchObject({ to: b, selfVi: "bố", status: "locked" });
  });

  it("asks again after a snooze, never after 'unknown'", () => {
    const mem = read([{ lines: [line("r1", "Kenta", "Yui"), line("r2", "Yui", "Kenta")] }]);
    const [q] = castQuestions(mem, pos(1), 1, { gender: 99, pair: 2 });
    const later = answerCast(mem, q, "later", pos(1));
    expect(castQuestions(later, pos(5), 1, { gender: 99, pair: 2 })).toEqual([]);
    expect(castQuestions(later, pos(11), 1, { gender: 99, pair: 2 })).toHaveLength(1);
    const never = answerCast(mem, q, "unknown", pos(1));
    expect(castQuestions(never, pos(30), 1, { gender: 99, pair: 2 })).toEqual([]);
  });
});
