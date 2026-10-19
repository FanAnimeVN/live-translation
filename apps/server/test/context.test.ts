import { describe, expect, it } from "vitest";
import { stripSpoilers, titleSimilarity } from "../src/context";

describe("metadata safety", () => {
  it("removes AniList spoiler blocks and markup", () => {
    const text = "A shy student. ~!She is secretly the villain's sister.!~<br><br>(Source: Example)";
    expect(stripSpoilers(text)).toBe("A shy student.");
  });

  it("scores exact titles high and unrelated fuzzy matches low", () => {
    expect(titleSimilarity("Aisazu ni wa Irarenai", "Aisazu ni wa Irarenai")).toBe(1);
    expect(titleSimilarity("うちの猫ず日記", "オフ会の姫 誰のもの???")).toBeLessThan(0.3);
  });
});
