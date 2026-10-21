/**
 * The reader's own chapter: image files, a folder or a ZIP, read in the browser.
 * ZIP entries are inflated with the browser's DecompressionStream (no extra library).
 */

const IMAGE = /\.(jpe?g|png|webp|gif|bmp|avif)$/i;

export interface PageFile {
  name: string;
  blob: Blob;
}

/** "page2" before "page10". */
export const naturalCompare = (a: string, b: string) => a.localeCompare(b, undefined, { numeric: true, sensitivity: "base" });

async function inflateRaw(data: Uint8Array): Promise<Uint8Array> {
  const stream = new Blob([data as BlobPart]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

/** Images inside a ZIP (stored or deflated entries), read from its central directory. */
export async function readZip(file: Blob): Promise<PageFile[]> {
  const buf = new Uint8Array(await file.arrayBuffer());
  const dv = new DataView(buf.buffer);
  let eocd = -1;
  for (let i = buf.length - 22; i >= Math.max(0, buf.length - 65557); i--) {
    if (dv.getUint32(i, true) === 0x06054b50) {
      eocd = i;
      break;
    }
  }
  if (eocd < 0) throw new Error("File ZIP không hợp lệ");
  const count = dv.getUint16(eocd + 10, true);
  let p = dv.getUint32(eocd + 16, true);
  const out: PageFile[] = [];
  const utf8 = new TextDecoder();
  for (let n = 0; n < count; n++) {
    if (dv.getUint32(p, true) !== 0x02014b50) break;
    const method = dv.getUint16(p + 10, true);
    const size = dv.getUint32(p + 20, true);
    const nameLen = dv.getUint16(p + 28, true);
    const extraLen = dv.getUint16(p + 30, true);
    const commentLen = dv.getUint16(p + 32, true);
    const local = dv.getUint32(p + 42, true);
    const name = utf8.decode(buf.subarray(p + 46, p + 46 + nameLen));
    p += 46 + nameLen + extraLen + commentLen;
    if (!IMAGE.test(name) || name.includes("__MACOSX/")) continue;
    const start = local + 30 + dv.getUint16(local + 26, true) + dv.getUint16(local + 28, true);
    const raw = buf.subarray(start, start + size);
    const data = method === 0 ? raw : method === 8 ? await inflateRaw(raw) : undefined;
    if (data) out.push({ name, blob: new Blob([data as BlobPart]) });
  }
  return out.sort((a, b) => naturalCompare(a.name, b.name));
}

/** Pages from a file picker or a folder picker, in natural order; ZIPs are opened. */
export async function collectPages(files: File[]): Promise<PageFile[]> {
  const out: PageFile[] = [];
  for (const f of [...files].sort((a, b) => naturalCompare(a.webkitRelativePath || a.name, b.webkitRelativePath || b.name))) {
    if (/\.zip$/i.test(f.name)) out.push(...(await readZip(f)));
    else if (IMAGE.test(f.name)) out.push({ name: f.webkitRelativePath || f.name, blob: f });
  }
  return out;
}

/** A short title from the folder or ZIP name. */
export function guessTitle(files: File[]): string {
  const f = files[0];
  if (!f) return "";
  const dir = f.webkitRelativePath?.split("/")[0];
  return (dir || f.name.replace(/\.(zip|jpe?g|png|webp)$/i, "")).replace(/[_]+/g, " ").trim();
}

/**
 * Re-encode as JPEG with the long side at most `maxSide` px: a phone photo or a 4K scan becomes
 * ~300–600 KB, so uploads through a tunnel stay quick. The model sees at most 1568 px anyway.
 */
export async function shrink(blob: Blob, maxSide = 2000): Promise<Blob> {
  const bmp = await createImageBitmap(blob);
  const s = Math.min(1, maxSide / Math.max(bmp.width, bmp.height));
  if (s === 1 && blob.size < 1.5 * 1024 * 1024 && /jpe?g/.test(blob.type)) return blob;
  const canvas = new OffscreenCanvas(Math.round(bmp.width * s), Math.round(bmp.height * s));
  const ctx = canvas.getContext("2d")!;
  ctx.fillStyle = "#fff";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(bmp, 0, 0, canvas.width, canvas.height);
  bmp.close();
  return canvas.convertToBlob({ type: "image/jpeg", quality: 0.9 });
}
