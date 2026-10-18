import { createCanvas, loadImage, type Canvas, type SKRSContext2D } from "@napi-rs/canvas";
import { drawMarks, type Ctx2D } from "@lt/render";
import { needsCrop, type TextRegion } from "@lt/core";

export interface DecodedPage {
  w: number;
  h: number;
  canvas: Canvas;
  ctx: SKRSContext2D;
}

export async function decodeImage(bytes: Buffer): Promise<DecodedPage> {
  const img = await loadImage(bytes);
  const canvas = createCanvas(img.width, img.height);
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, img.width, img.height);
  ctx.drawImage(img, 0, 0);
  return { w: img.width, h: img.height, canvas, ctx };
}

const MAX_SIDE = 1568;

/** Page with outlined, numbered regions, downscaled to the model's comfortable size. */
export async function markedPageDataUrl(page: DecodedPage, regions: TextRegion[], highlight?: string[]): Promise<string> {
  const scale = Math.min(1, MAX_SIDE / Math.max(page.w, page.h));
  const w = Math.round(page.w * scale);
  const h = Math.round(page.h * scale);
  const canvas = createCanvas(w, h);
  const ctx = canvas.getContext("2d");
  ctx.drawImage(page.canvas, 0, 0, w, h);
  const scaled = regions
    .filter((r) => !highlight || highlight.includes(r.id))
    .map((r) => ({ ...r, box: { x: r.box.x * scale, y: r.box.y * scale, w: r.box.w * scale, h: r.box.h * scale } }));
  drawMarks(ctx as unknown as Ctx2D, scaled, w);
  return toDataUrl(canvas);
}

/** Zoomed crops for small or thin regions (or the given ids). */
export async function regionCrops(page: DecodedPage, regions: TextRegion[], ids?: string[]): Promise<Array<{ id: string; dataUrl: string }>> {
  const out: Array<{ id: string; dataUrl: string }> = [];
  for (const r of regions) {
    if (ids ? !ids.includes(r.id) : !needsCrop(r)) continue;
    const m = 6;
    const x = Math.max(0, Math.floor(r.box.x - m));
    const y = Math.max(0, Math.floor(r.box.y - m));
    const w = Math.min(page.w - x, Math.ceil(r.box.w + 2 * m));
    const h = Math.min(page.h - y, Math.ceil(r.box.h + 2 * m));
    const zoom = Math.max(1, Math.min(3, 200 / Math.min(w, h), 768 / Math.max(w, h)));
    const canvas = createCanvas(Math.round(w * zoom), Math.round(h * zoom));
    const ctx = canvas.getContext("2d");
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(page.canvas, x, y, w, h, 0, 0, canvas.width, canvas.height);
    out.push({ id: r.id, dataUrl: await toDataUrl(canvas) });
  }
  return out;
}

async function toDataUrl(canvas: Canvas): Promise<string> {
  const jpeg = await canvas.encode("jpeg", 90);
  return `data:image/jpeg;base64,${jpeg.toString("base64")}`;
}
