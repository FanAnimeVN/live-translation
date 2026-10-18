import type { Box } from "./types";

/**
 * Recursive XY-cut reading order. Rows (horizontal gaps) are read top to bottom,
 * columns inside a row right to left for manga (rtl). This is only the initial
 * numbering; the model reports the natural order it actually read.
 */
export function xyCutOrder(boxes: Box[], rtl = true): number[] {
  const out: number[] = [];
  const recurse = (ids: number[]) => {
    if (ids.length <= 1) {
      out.push(...ids);
      return;
    }
    const rows = splitByGaps(ids, (i) => [boxes[i].y, boxes[i].y + boxes[i].h]);
    if (rows.length > 1) {
      rows.forEach(recurse);
      return;
    }
    const cols = splitByGaps(ids, (i) => [boxes[i].x, boxes[i].x + boxes[i].w]);
    if (cols.length > 1) {
      (rtl ? cols.reverse() : cols).forEach(recurse);
      return;
    }
    const rightEdge = (i: number) => boxes[i].x + boxes[i].w;
    ids.sort((a, b) => (rtl ? rightEdge(b) - rightEdge(a) : boxes[a].x - boxes[b].x) || boxes[a].y - boxes[b].y);
    out.push(...ids);
  };
  recurse(boxes.map((_, i) => i));
  return out;
}

function splitByGaps(ids: number[], interval: (i: number) => [number, number]): number[][] {
  const sorted = [...ids].sort((a, b) => interval(a)[0] - interval(b)[0]);
  const groups: number[][] = [];
  let end = -Infinity;
  for (const id of sorted) {
    const [s, e] = interval(id);
    if (groups.length && s < end - 1) {
      groups[groups.length - 1].push(id);
      end = Math.max(end, e);
    } else {
      groups.push([id]);
      end = e;
    }
  }
  return groups;
}
