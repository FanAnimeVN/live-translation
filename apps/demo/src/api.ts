import type { PageResult, ReadingPosition, SeriesMemory, TranslateEvent, EntryStatus } from "@lt/core";

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

async function json<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return (await res.json()) as T;
}

export const api = {
  pages: () => json<PageInfo[]>("/api/pages"),
  models: () => json<{ models: ModelInfo[]; default: string }>("/api/models"),
  budget: () => json<{ spentUsd: number; limitUsd: number }>("/api/budget"),
  cached: (pageId: string, model: string, ns: string) =>
    json<{ result: PageResult | null; ms: number }>(`/api/result?${new URLSearchParams({ pageId, model, ns })}`),
  memory: (seriesId: string, ns: string, title: string) =>
    json<SeriesMemory>(`/api/memory?${new URLSearchParams({ seriesId, ns, title })}`),
  setEntity: (body: { ns: string; seriesId: string; ja: string; status: EntryStatus; vi?: string }) =>
    json<SeriesMemory>("/api/memory/entity", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
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
  if (!res.ok || !res.body) throw new Error(`${res.status} ${await res.text()}`);
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
