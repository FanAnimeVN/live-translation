import { describe, expect, it } from "vitest";
import {
  applyDigests,
  applyMemoryUpdate,
  arcDigestsDue,
  ARC_CHAPTERS,
  atOrBefore,
  backgroundInput,
  chapterDigestsDue,
  digestInput,
  emptyMemory,
  estimateTokens,
  makeDigest,
  makeOverview,
  MEMORY_BUDGET,
  mergePage,
  overviewDue,
  overviewSources,
  PS_MIN_CHAPTERS,
  psWorthy,
  RECALL_MIN_CHAPTERS,
  recallContext,
  recallEvents,
  volatileContext,
  type Evidence,
  type ReadingPosition,
  type RegionTranslation,
  type SeriesMemory,
  type StoryEvent,
  type SummaryRecord,
} from "../src";

const pos = (chapter: number, page: number): ReadingPosition => ({ chapter, page });
const ev = (chapter: number, page: number, regionId = "r1"): Evidence => ({ pageId: `c${chapter}p${page}`, regionId, pos: pos(chapter, page) });
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
const cardAt = (chapter: number, page: number, text: string, over: Partial<StoryEvent> = {}): StoryEvent => ({ text, pos: pos(chapter, page), evidence: [ev(chapter, page)], ...over });
const record = (events: StoryEvent[], segment = "", story?: string): SummaryRecord => ({
  from: events[0]?.pos ?? pos(1, 1),
  upTo: events.reduce((a, e) => (atOrBefore(a, e.pos) ? e.pos : a), events[0]?.pos ?? pos(1, 1)),
  segment,
  ...(story !== undefined ? { story } : {}),
  events,
  model: "m",
  at: "",
});
const withCards = (cards: StoryEvent[], extra: Partial<SeriesMemory> = {}): SeriesMemory => ({
  ...emptyMemory("s", "S"),
  archive: cards.map((c) => record([c], `seg ${c.pos.chapter}.${c.pos.page}`)),
  ...extra,
});

describe("L1 event cards (v4)", () => {
  it("keeps who / importance / kind / keys and drops invalid values", () => {
    let mem = emptyMemory("s", "S");
    mem = mergePage(mem, "p3", pos(1, 3), { names: [], address: [], missed: [] }, [line("r2", "お祭りで約束したよね", "Mình đã hứa ở lễ hội mà", "Nana", "Sota")]).memory;
    mem = applyMemoryUpdate(
      mem,
      {
        segment: "Nana và Sota hứa hẹn.",
        events: [
          { text: "Nana hứa với Sota ở lễ hội", who: ["Nana", "Sota", "unknown"], importance: 3, kind: "promise", keys: ["約束", "お祭り", "lời hứa", "lễ hội"], evidence: ["p3:r2"] },
          { text: "Một sự kiện lạ", who: "Nana" as unknown as string[], importance: 7, kind: "battle", keys: [42 as unknown as string], evidence: ["p3:r2"] },
        ],
      },
      pos(1, 3),
      "m",
    );
    const [a, b] = mem.archive![0].events;
    expect(a).toMatchObject({ who: ["Nana", "Sota"], importance: 3, kind: "promise", keys: ["約束", "お祭り", "lời hứa", "lễ hội"] });
    expect(a.evidence[0]).toMatchObject({ pageId: "p3", regionId: "r2", pos: pos(1, 3) });
    expect(b).toEqual({ text: "Một sự kiện lạ", pos: pos(1, 3), evidence: [{ pageId: "p3", regionId: "r2", pos: pos(1, 3) }] });
  });

  it("loads a v3 memory (rolling story, bare cards) and can still recall from it", () => {
    const v3 = JSON.parse(
      JSON.stringify({
        seriesId: "s",
        title: "S",
        entities: [],
        address: [],
        recent: [],
        updatedAt: "",
        summary: { text: "Chuyện cũ.", upTo: pos(1, 4), events: [cardAt(1, 2, "Nana đánh rơi chìa khóa")], updatedAt: "" },
        archive: [{ from: pos(1, 1), upTo: pos(1, 4), segment: "Nana mất chìa khóa.", story: "Nana mất chìa khóa ở trường.", events: [cardAt(1, 2, "Nana đánh rơi chìa khóa")], model: "m", at: "" }],
      }),
    ) as SeriesMemory;
    expect(volatileContext(v3, pos(1, 6))).toContain("Nana mất chìa khóa ở trường."); // legacy story still shown
    expect(volatileContext(v3, pos(1, 3))).not.toContain("ở trường"); // but never before it was written
    const hits = recallEvents(v3, pos(1, 6), { keys: ["chìa khóa"] });
    expect(hits.map((h) => h.event.text)).toEqual(["Nana đánh rơi chìa khóa"]);
    expect(hits[0].at).toEqual(pos(1, 2));
  });
});

describe("L2 chapter digests and L3 overview", () => {
  it("a finished chapter is digested from its own cards only", () => {
    const mem = withCards([cardAt(1, 2, "A gặp B"), cardAt(1, 9, "A hứa với B", { kind: "promise", importance: 3, who: ["A", "B"] }), cardAt(2, 1, "C xuất hiện")]);
    const due = chapterDigestsDue(mem);
    expect(due.map((d) => [d.chapter, d.finished])).toEqual([[1, true]]); // chapter 2 is open and young
    const input = digestInput(due[0].cards);
    expect(input).toContain("A hứa với B");
    expect(input).toContain("[promise, 3] (A, B)");
    expect(input).not.toContain("C xuất hiện");
    const d = makeDigest("chapter", [1, 1], "A gặp B và hứa.", due[0].cards, "m");
    expect(d.upTo).toEqual(pos(1, 9));
    const after = applyDigests(mem, [d]);
    expect(chapterDigestsDue(after)).toEqual([]);
    expect(overviewDue(after)).toBe(true);
    // Late cards for chapter 1 make its digest stale again.
    const late = { ...after, archive: [...after.archive!, record([cardAt(1, 10, "B khóc")])] };
    expect(chapterDigestsDue(late).map((x) => x.chapter)).toEqual([1]);
  });

  it("the open chapter gets a digest once its start has left the latest developments", () => {
    const cards = Array.from({ length: 8 }, (_, i) => cardAt(1, i + 1, `Sự kiện ${i + 1}`));
    const few = withCards(cards.slice(0, 3));
    expect(chapterDigestsDue(few)).toEqual([]);
    const many = withCards(cards);
    expect(chapterDigestsDue(many).map((d) => [d.chapter, d.finished, d.cards.length])).toEqual([[1, false, 8]]);
    const digested = applyDigests(many, [makeDigest("chapter", [1, 1], "Tám sự kiện.", cards, "m")]);
    expect(chapterDigestsDue(digested)).toEqual([]);
    expect(overviewDue(digested)).toBe(false); // L3 waits for a finished chapter
    const ctx = volatileContext(digested, pos(1, 9));
    expect(ctx).toContain("This chapter so far (chapter 1, up to page 8)");
    expect(ctx).not.toContain("seg 1.7"); // segments the digest covers are not repeated
    expect(volatileContext(digested, pos(1, 5))).not.toContain("Tám sự kiện"); // written from later pages
  });

  it("L3 is built from digests (arcs for long series), never from the previous overview", () => {
    const chapters = 25;
    let mem = withCards(Array.from({ length: chapters }, (_, i) => cardAt(i + 1, 5, `Chương ${i + 1}`)));
    mem = applyDigests(
      mem,
      Array.from({ length: chapters - 1 }, (_, i) => makeDigest("chapter", [i + 1, i + 1], `Tóm tắt chương ${i + 1}`, [cardAt(i + 1, 5, "x")], "m")),
    );
    mem = applyDigests(mem, [], makeOverview("OLD OVERVIEW", overviewSources(mem, pos(3, 1)), "m"));
    const arcs = arcDigestsDue(mem);
    expect(arcs.map((a) => a.chapters)).toEqual([
      [1, ARC_CHAPTERS],
      [ARC_CHAPTERS + 1, 2 * ARC_CHAPTERS],
    ]);
    mem = applyDigests(mem, arcs.map((a) => makeDigest("arc", a.chapters, `Arc ${a.chapters[0]}`, a.digests, "m")));
    const src = overviewSources(mem, pos(chapters, 1));
    expect(src.map((d) => `${d.level}:${d.chapters.join("-")}`)).toEqual(["arc:1-10", "arc:11-20", "chapter:21-21", "chapter:22-22", "chapter:23-23", "chapter:24-24"]);
    expect(digestInput(src)).not.toContain("OLD OVERVIEW");
    expect(overviewDue(mem)).toBe(true);
    const ov = makeOverview("Toàn truyện", src, "m");
    expect(ov).toMatchObject({ chapter: 24, upTo: pos(24, 5) });
    mem = applyDigests(mem, [], ov);
    expect(overviewDue(mem)).toBe(false);
    // Re-reading chapter 3 gets the overview as it stood then, not the latest one.
    expect(volatileContext(mem, pos(3, 2))).toContain("OLD OVERVIEW");
    expect(volatileContext(mem, pos(3, 2))).not.toContain("Toàn truyện");
    expect(volatileContext(mem, pos(25, 2))).toContain("Toàn truyện");
    expect(volatileContext(mem, pos(25, 2))).toContain("Previous chapter (chapter 24)");
  });

  it("keeps the per-page context within the same budget for chapter 1 and chapter 500", () => {
    const long = "Một câu dài về chuyện đã xảy ra trong chương này. ".repeat(20);
    let mem = withCards(Array.from({ length: 500 }, (_, i) => cardAt(i + 1, 3, long)));
    mem = applyDigests(mem, Array.from({ length: 499 }, (_, i) => makeDigest("chapter", [i + 1, i + 1], long, [cardAt(i + 1, 3, "x")], "m")), makeOverview(long, [makeDigest("chapter", [499, 499], "x", [cardAt(499, 3, "x")], "m")], "m"));
    for (let i = 0; i < 80; i++) mem = mergePage(mem, `p${i}`, pos(500, 4 + i), { names: [], address: [], missed: [] }, [line("r1", "やあ".repeat(10), "Chào ".repeat(10), "A", "B")]).memory;
    const ctx = volatileContext(mem, pos(500, 90));
    expect(estimateTokens(ctx)).toBeLessThanOrEqual(MEMORY_BUDGET.volatile);
    expect(ctx).toContain("Story so far (chapters 1–499");
    expect(ctx).toContain("Previous chapter (chapter 499)");
    expect(ctx).toContain("Recent dialogue");
    expect(JSON.stringify(backgroundInput(mem)).length).toBeLessThan(6000);
  });

  it("K bounds the recent dialogue (L0)", () => {
    let mem = emptyMemory("s", "S");
    for (let i = 1; i <= 50; i++) mem = mergePage(mem, `p${i}`, pos(1, i), { names: [], address: [], missed: [] }, [line("r1", `行${i}`, `dòng ${i}`)]).memory;
    const count = (k: number) => (volatileContext(mem, pos(1, 50), 1e9, { recentLines: k, recentTokens: 1e9 }).match(/=> dòng/g) ?? []).length;
    expect([0, 10, 20, 40].map(count)).toEqual([0, 10, 20, 40]);
    expect(count(80)).toBe(50); // only 50 lines read so far
    expect(volatileContext(mem, pos(1, 50))).toContain("dòng 50");
  });
});

describe("recallEvents", () => {
  const cards = [
    cardAt(1, 3, "Nana hứa với Sota sẽ cùng đi lễ hội", { who: ["Nana", "Sota"], importance: 3, kind: "promise", keys: ["約束", "お祭り", "lời hứa", "lễ hội"] }),
    cardAt(1, 8, "Nana ăn bánh", { who: ["Nana"], importance: 1, keys: ["ケーキ", "bánh"] }),
    cardAt(2, 4, "Sota nhớ lại lời hứa", { who: ["Sota"], importance: 2, kind: "flashback", keys: ["約束"] }),
    cardAt(3, 7, "Nana tiết lộ bí mật", { who: ["Nana"], importance: 3, kind: "reveal", keys: ["秘密", "bí mật"] }),
  ];
  const mem = withCards(cards);

  it("ranks by people and keyword overlap, then importance", () => {
    const hits = recallEvents(mem, pos(4, 1), { who: ["Nana"], keys: ["約束"] });
    expect(hits.map((h) => h.event.text)).toEqual(["Nana hứa với Sota sẽ cùng đi lễ hội", "Sota nhớ lại lời hứa"]);
    expect(hits[0].at).toEqual(pos(1, 3));
    expect(hits[0].pageId).toBe("c1p3");
  });

  it("a P/S only for an important event dozens of chapters back; the recall pass skips the open chapter", () => {
    const m = withCards([
      cardAt(1, 3, "Nana hứa với Sota sẽ cùng đi lễ hội", { importance: 3, keys: ["約束"] }),
      cardAt(1, 5, "Nana làm rơi ô", { importance: 1, keys: ["約束"] }),
      cardAt(30, 2, "Sota nhắc lại lời hứa", { importance: 2, keys: ["約束"] }),
    ]);
    const at = pos(30, 9);
    const hits = recallEvents(m, at, { keys: ["約束"], minChaptersBack: RECALL_MIN_CHAPTERS });
    expect(hits.map((h) => h.event.text).sort()).toEqual(["Nana hứa với Sota sẽ cùng đi lễ hội", "Nana làm rơi ô"]); // chapter 30 itself is already in the prompt
    const worthy = hits.filter((h) => psWorthy(h, at)).map((h) => h.event.text);
    expect(worthy).toEqual(["Nana hứa với Sota sẽ cùng đi lễ hội"]); // the minor one gets no note
    // Ten chapters later is too soon to have forgotten.
    expect(recallEvents(m, pos(11, 1), { keys: ["約束"] }).filter((h) => psWorthy(h, pos(11, 1)))).toEqual([]);
    expect(PS_MIN_CHAPTERS).toBeGreaterThanOrEqual(20);
  });

  it("matches names through the cast table, and never merges two separate characters", () => {
    const entity = (ja: string, vi: string, old: string[] = []) => ({
      ja,
      vi,
      kind: "character" as const,
      status: "auto" as const,
      knownFrom: pos(1, 2),
      evidence: [ev(1, 2)],
      history: old.map((o) => ({ at: "", vi: o, status: "auto" as const })),
    });
    const m = withCards(
      [
        cardAt(1, 2, "Nora-tora bị tiêm thuốc", { who: ["Nora-tora"], keys: ["注射", "tiêm"] }),
        cardAt(1, 3, "Nora-boss tuyên bố làm chủ khu phố", { who: ["Nora-boss"], keys: ["ボス"] }),
      ],
      { entities: [entity("ノラトラ", "Nora-tora", ["Tora"]), entity("ノラボス", "Nora-boss")] },
    );
    const texts = (q: Parameters<typeof recallEvents>[2]) => recallEvents(m, pos(1, 9), { ...q, minPagesBack: 5 }).map((h) => h.event.text);
    // The line names the cat in Japanese; the card names it in Vietnamese.
    expect(texts({ who: ["ノラトラ"], keys: ["ノラトラ"] })).toEqual(["Nora-tora bị tiêm thuốc"]);
    // An earlier rendering the reader changed still finds it.
    expect(texts({ who: ["Tora"], keys: ["Tora"] })).toEqual(["Nora-tora bị tiêm thuốc"]);
    // Nora-boss is another entry: no link is invented between the two.
    expect(texts({ who: ["ノラトラ"], keys: ["ボス"] })).toEqual(["Nora-boss tuyên bố làm chủ khu phố"]);
    expect(texts({ who: ["Nora-tora"], keys: ["Nora-tora"] })).not.toContain("Nora-boss tuyên bố làm chủ khu phố");
  });

  it("needs a keyword hit when keywords are given; a card key inside the line counts", () => {
    expect(recallEvents(mem, pos(4, 1), { who: ["Nana"], keys: ["宇宙"] })).toEqual([]);
    const byText = recallEvents(mem, pos(4, 1), { text: "あの秘密、まだ覚えてる？" });
    expect(byText.map((h) => h.event.text)).toEqual(["Nana tiết lộ bí mật"]);
    expect(recallEvents(mem, pos(4, 1), { who: ["Nana"] }).length).toBe(3); // people alone, when nothing else is known
  });

  it("never returns a card from after the reading position (exhaustive over positions)", () => {
    const rand = (() => {
      let x = 7;
      return () => ((x = (x * 1103515245 + 12345) % 2147483648) / 2147483648);
    })();
    const many: StoryEvent[] = Array.from({ length: 120 }, (_, i) => {
      const c = 1 + Math.floor(rand() * 6);
      const p = 1 + Math.floor(rand() * 20);
      // Some cards cite a later page as extra evidence: they must stay hidden until then.
      const extra = rand() < 0.3 ? [ev(c, Math.min(20, p + 1 + Math.floor(rand() * 5)), "r9")] : [];
      const evidence = [ev(c, p), ...extra];
      const last = evidence.reduce((a, e) => (atOrBefore(a, e.pos) ? e.pos : a), evidence[0].pos);
      return { text: `sự kiện ${i} 約束`, pos: last, evidence, who: ["Nana"], keys: ["約束"], importance: (1 + (i % 3)) as 1 | 2 | 3 };
    });
    const big = withCards(many);
    for (let c = 1; c <= 7; c++)
      for (let p = 1; p <= 21; p++) {
        const at = pos(c, p);
        for (const h of recallEvents(big, at, { who: ["Nana"], keys: ["約束"] }, 50, )) {
          expect(atOrBefore(h.event.pos, at)).toBe(true);
          for (const e of h.event.evidence) expect(atOrBefore(e.pos, at)).toBe(true);
          expect(h.at.chapter === c && h.at.page === p).toBe(false); // earlier pages only
        }
      }
    expect(recallEvents(big, pos(1, 1), { keys: ["約束"] }, 50)).toEqual([]);
  });

  it("does not leak later cards through a later-dated position on the same chapter", () => {
    expect(recallEvents(mem, pos(3, 6), { keys: ["秘密"] })).toEqual([]);
    expect(recallEvents(mem, pos(3, 8), { keys: ["秘密"] }).length).toBe(1);
    expect(recallEvents(mem, pos(3, 7), { keys: ["秘密"] })).toEqual([]); // the same page is not an "earlier event"
    expect(recallEvents(mem, pos(3, 7), { keys: ["秘密"], includeCurrentPage: true }).length).toBe(1);
  });

  it("with a minimum gap, skips events a few pages back in the same chapter but keeps earlier chapters", () => {
    const q = { keys: ["約束"], minPagesBack: 5 };
    expect(recallEvents(mem, pos(1, 7), q)).toEqual([]); // the promise was 4 pages ago
    expect(recallEvents(mem, pos(1, 8), q).map((h) => h.event.text)).toEqual(["Nana hứa với Sota sẽ cùng đi lễ hội"]);
    expect(recallEvents(mem, pos(2, 6), q).map((h) => h.at)).toEqual([pos(1, 3)]); // chapter 2 page 4 is too close
    expect(recallEvents(mem, pos(3, 1), q).map((h) => h.at)).toEqual([pos(1, 3), pos(2, 4)]); // the turning point ranks first
  });

  it("formats cards with ids and where they happened, within the recall budget", () => {
    const hits = recallEvents(mem, pos(4, 1), { who: ["Nana"], keys: ["約束"] });
    const ctx = recallContext(hits);
    expect(ctx.split("\n")[0]).toBe("c1 (chapter 1, page 3; promise; Nana, Sota): Nana hứa với Sota sẽ cùng đi lễ hội [keys: 約束, お祭り, lời hứa, lễ hội]");
    const long = withCards(Array.from({ length: 30 }, (_, i) => cardAt(1, i + 1, "Một sự kiện rất dài ".repeat(20) + "約束", { keys: ["約束"] })));
    expect(estimateTokens(recallContext(recallEvents(long, pos(2, 1), { keys: ["約束"] }, 30)))).toBeLessThanOrEqual(MEMORY_BUDGET.recall);
  });
});
