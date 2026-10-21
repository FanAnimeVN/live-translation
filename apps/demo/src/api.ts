import type { CastAnswer, CastQuestion, PageResult, ReadingPosition, SeriesMemory, TranslateEvent, EntryStatus } from "@lt/core";

export interface PageInfo {
  id: string;
  title: string;
  seriesId: string;
  file: string;
  size: { w: number; h: number };
  position: ReadingPosition;
  gtCount: number;
}

export interface ModelInfo {
  id: string;
  label: string;
  tier: string;
  inUsd: number;
  outUsd: number;
}

/** Server error with its message shown as is (e.g. "Hết lượt hôm nay"). */
async function failure(res: Response): Promise<Error> {
  const text = await res.text();
  try {
    return Object.assign(new Error(JSON.parse(text).error ?? text), { status: res.status });
  } catch {
    return Object.assign(new Error(`${res.status} ${text}`), { status: res.status });
  }
}

async function json<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) throw await failure(res);
  return (await res.json()) as T;
}

export interface Budget {
  spentUsd?: number;
  limitUsd?: number;
  /** Share mode: the invite's name and today's remaining pages. */
  share?: { name: string; pagesLeft: number; dailyPages: number };
}

export const api = {
  health: () => json<{ ok: boolean; share: boolean }>("/api/health"),
  invite: (code: string) =>
    json<{ name: string; pagesLeft: number }>("/api/invite", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code }) }),
  /** One page of the reader's own chapter; the server keeps the image in memory only. */
  upload: (blob: Blob, meta: { title: string; chapter: number; index: number }) =>
    json<PageInfo>(`/api/upload?${new URLSearchParams({ title: meta.title, chapter: String(meta.chapter), index: String(meta.index) })}`, {
      method: "POST",
      headers: { "Content-Type": blob.type || "application/octet-stream" },
      body: blob,
    }),
  pages: () => json<PageInfo[]>("/api/pages"),
  models: () => json<{ models: ModelInfo[]; default: string }>("/api/models"),
  budget: () => json<Budget>("/api/budget"),
  cached: (pageId: string, model: string, ns: string) =>
    json<{ result: PageResult | null; ms: number }>(`/api/result?${new URLSearchParams({ pageId, model, ns })}`),
  memory: (seriesId: string, ns: string, title: string) =>
    json<SeriesMemory>(`/api/memory?${new URLSearchParams({ seriesId, ns, title })}`),
  setEntity: (body: { ns: string; seriesId: string; ja: string; status: EntryStatus; vi?: string }) =>
    json<SeriesMemory>("/api/memory/entity", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  questions: (seriesId: string, ns: string, pos: ReadingPosition) =>
    json<{ questions: Array<CastQuestion & { sample: Array<{ speaker: string; to?: string; ja: string; vi: string }> }> }>(
      `/api/memory/questions?${new URLSearchParams({ seriesId, ns, chapter: String(pos.chapter), page: String(pos.page) })}`,
    ),
  answer: (body: { ns: string; seriesId: string; question: CastQuestion; answer: CastAnswer; pos: ReadingPosition }) =>
    json<SeriesMemory>("/api/memory/answer", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  resetMemory: (body: { ns: string; seriesId: string; title: string }) =>
    json<{ ok: boolean }>("/api/memory/reset", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  inpaint: (body: { pageId: string; model: string; ns: string; ids: string[] }) =>
    json<{ patches: Array<{ id: string; x: number; y: number; w: number; h: number; dataUrl: string; coverage: number; ms: number; textBoxes: Array<{ x: number; y: number; w: number; h: number }>; textExtent?: { x: number; y: number; w: number; h: number }; ink?: [number, number, number]; outline?: [number, number, number]; keepOut?: Array<{ x: number; y: number; w: number; h: number }> }>; ms: number; rejected?: Array<{ id: string; reason: string }> }>(
      "/api/inpaint",
      { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) },
    ),
  imageUrl: (pageId: string) => `/api/pages/${encodeURIComponent(pageId)}/image`,
};

/** POST /api/translate and dispatch each NDJSON event as it streams in. */
export async function translateStream(
  body: { pageId: string; model: string; ns: string; inpaint?: boolean },
  onEvent: (e: TranslateEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch("/api/translate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) throw await failure(res);
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += value;
    let nl: number;
    while ((nl = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, nl).trim();
      buf = buf.slice(nl + 1);
      if (line) onEvent(JSON.parse(line) as TranslateEvent);
    }
  }
  if (buf.trim()) onEvent(JSON.parse(buf) as TranslateEvent);
}
