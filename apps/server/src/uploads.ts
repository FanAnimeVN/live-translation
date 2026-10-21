import { randomUUID } from "node:crypto";
import { getPage, readPageImage, type DatasetPage } from "./dataset";
import { decodeImage } from "./image";

/**
 * Pages a reader opens from their own files (images, a folder, a ZIP). The image stays in this
 * process's memory only, never on disk; translations are cached as text + geometry like any page.
 * Ids start with "up:" so the same routes serve dataset pages and uploaded pages.
 */
interface Upload {
  page: DatasetPage;
  bytes: Buffer;
  /** Invite code of the reader who uploaded it (share mode); undefined on the team's own server. */
  owner?: string;
  at: number;
}

const store = new Map<string, Upload>();
const MAX_BYTES = 600 * 1024 * 1024;
const TTL_MS = 12 * 3600 * 1000;
export const MAX_UPLOAD_BYTES = 12 * 1024 * 1024;

function evict() {
  const now = Date.now();
  for (const [id, u] of store) if (now - u.at > TTL_MS) store.delete(id);
  let total = [...store.values()].reduce((a, u) => a + u.bytes.length, 0);
  for (const [id, u] of store) {
    if (total <= MAX_BYTES) break;
    store.delete(id);
    total -= u.bytes.length;
  }
}

const slug = (s: string) =>
  s
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9぀-ヿ一-鿿]+/g, "-")
    .replace(/^-|-$/g, "") || "truyen";

export async function addUpload(bytes: Buffer, meta: { title: string; chapter: number; index: number }, owner?: string): Promise<DatasetPage> {
  const d = await decodeImage(bytes);
  const id = `up:${randomUUID().replace(/-/g, "").slice(0, 16)}`;
  const title = meta.title.trim().slice(0, 120) || "Truyện của tôi";
  const page: DatasetPage = {
    id,
    set: "upload",
    root: "",
    title,
    seriesId: `up-${slug(title)}`,
    file: "",
    size: { w: d.w, h: d.h },
    position: { chapter: Math.max(1, Math.floor(meta.chapter) || 1), page: Math.max(1, Math.floor(meta.index) || 1) },
    gt: [],
  };
  evict();
  store.set(id, { page, bytes, owner, at: Date.now() });
  return page;
}

export function listUploads(owner?: string): DatasetPage[] {
  evict();
  return [...store.values()]
    .filter((u) => u.owner === owner)
    .map((u) => u.page)
    .sort((a, b) => a.title.localeCompare(b.title) || a.position.chapter - b.position.chapter || a.position.page - b.position.page);
}

/** A dataset page, or an uploaded page the caller owns. With `onlyUploads`, dataset pages are not reachable. */
export async function findPage(id: string, owner?: string, onlyUploads = false): Promise<DatasetPage> {
  if (id.startsWith("up:")) {
    const u = store.get(id);
    if (!u || u.owner !== owner) throw new Error("Trang không còn trong bộ nhớ (mở lại chương)");
    u.at = Date.now();
    return u.page;
  }
  if (onlyUploads) throw new Error(`Unknown page ${id}`);
  return getPage(id);
}

export async function pageBytes(page: DatasetPage): Promise<Buffer> {
  const u = store.get(page.id);
  return u ? u.bytes : readPageImage(page);
}
