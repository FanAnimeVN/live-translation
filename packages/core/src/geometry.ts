import type { Box } from "./types";

export const area = (b: Box): number => Math.max(0, b.w) * Math.max(0, b.h);

export function fromXYXY(x1: number, y1: number, x2: number, y2: number): Box {
  return { x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.abs(x2 - x1), h: Math.abs(y2 - y1) };
}

export function intersect(a: Box, b: Box): Box | null {
  const x1 = Math.max(a.x, b.x);
  const y1 = Math.max(a.y, b.y);
  const x2 = Math.min(a.x + a.w, b.x + b.w);
  const y2 = Math.min(a.y + a.h, b.y + b.h);
  return x2 > x1 && y2 > y1 ? { x: x1, y: y1, w: x2 - x1, h: y2 - y1 } : null;
}

export function interArea(a: Box, b: Box): number {
  const i = intersect(a, b);
  return i ? area(i) : 0;
}

export function iou(a: Box, b: Box): number {
  const i = interArea(a, b);
  const u = area(a) + area(b) - i;
  return u > 0 ? i / u : 0;
}

/** Fraction of `inner` covered by `outer`. */
export function containment(inner: Box, outer: Box): number {
  const a = area(inner);
  return a > 0 ? interArea(inner, outer) / a : 0;
}

export function union(a: Box, b: Box): Box {
  const x1 = Math.min(a.x, b.x);
  const y1 = Math.min(a.y, b.y);
  const x2 = Math.max(a.x + a.w, b.x + b.w);
  const y2 = Math.max(a.y + a.h, b.y + b.h);
  return { x: x1, y: y1, w: x2 - x1, h: y2 - y1 };
}

export const center = (b: Box) => ({ x: b.x + b.w / 2, y: b.y + b.h / 2 });

export function containsPoint(b: Box, p: { x: number; y: number }): boolean {
  return p.x >= b.x && p.x <= b.x + b.w && p.y >= b.y && p.y <= b.y + b.h;
}

export function clampBox(b: Box, w: number, h: number): Box {
  const x1 = Math.max(0, Math.min(w, b.x));
  const y1 = Math.max(0, Math.min(h, b.y));
  const x2 = Math.max(0, Math.min(w, b.x + b.w));
  const y2 = Math.max(0, Math.min(h, b.y + b.h));
  return { x: x1, y: y1, w: x2 - x1, h: y2 - y1 };
}

export function expand(b: Box, px: number, bounds?: { w: number; h: number }): Box {
  const e = { x: b.x - px, y: b.y - px, w: b.w + 2 * px, h: b.h + 2 * px };
  return bounds ? clampBox(e, bounds.w, bounds.h) : e;
}

export function roundBox(b: Box): Box {
  const x = Math.floor(b.x);
  const y = Math.floor(b.y);
  return { x, y, w: Math.ceil(b.x + b.w) - x, h: Math.ceil(b.y + b.h) - y };
}

/** Box in 0..1000 page coordinates [x1, y1, x2, y2] for prompts. */
export function fromPermille(b: [number, number, number, number], w: number, h: number): Box {
  return { x: (b[0] / 1000) * w, y: (b[1] / 1000) * h, w: ((b[2] - b[0]) / 1000) * w, h: ((b[3] - b[1]) / 1000) * h };
}

export function toPermille(b: Box, w: number, h: number): [number, number, number, number] {
  const f = (v: number, d: number) => Math.max(0, Math.min(1000, Math.round((v / d) * 1000)));
  return [f(b.x, w), f(b.y, h), f(b.x + b.w, w), f(b.y + b.h, h)];
}
