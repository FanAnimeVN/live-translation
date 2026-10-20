import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { findGutters, type EntryStatus, type Gutter, type PageResult, type RecallNote, type RegionTranslation, type SeriesMemory, type TextRegion } from "@lt/core";
import { drawNotes, LETTERING_FONT, placeNotes, renderTranslation, type Ctx2D, type NotePlacement, type PatchImage, type RegionRender } from "@lt/render";
import { api, translateStream, type ModelInfo, type PageInfo } from "./api";

type Status = "idle" | "cached" | "detecting" | "translating" | "done" | "error";

interface PageState {
  regions: TextRegion[];
  translations: Record<string, RegionTranslation>;
  result?: PageResult;
  status: Status;
  error?: string;
  cacheMs?: number;
  live?: { detectMs?: number; firstMs?: number };
  /** P/S notes streamed by the recall pass (also in result.recall once done). */
  ps?: RecallNote[];
}

/** P/S for lines that refer back to earlier events: off, a tappable dot (default), or lettered in a gutter. */
type PsMode = "off" | "subtle" | "on";

const NS = "demo";
/** Pages translated ahead of the reader when prefetch is on. */
const PREFETCH_PAGES = 2;

/**
 * Rough cost of one page from the model's prices: ~4.5k input tokens (page image + context)
 * and ~1k output tokens (Claude Haiku 5.5 measured $0.00095/page on the 10 GT pages, 19/10).
 */
function estimatePageUsd(m: ModelInfo): number {
  return (m.inUsd * 4500 + m.outUsd * 1000) / 1e6;
}
const ROLE_VI: Record<string, string> = {
  dialogue: "Thoại",
  thought: "Suy nghĩ",
  narration: "Dẫn truyện",
  sign: "Chữ trên cảnh",
  sfx: "SFX",
  decorative: "Chữ phụ",
  none: "Không có chữ",
};

export function App() {
  const [pages, setPages] = useState<PageInfo[]>([]);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [model, setModel] = useState("");
  const [pageId, setPageId] = useState("");
  const [states, setStates] = useState<Record<string, PageState>>({});
  const [showOriginal, setShowOriginal] = useState(false);
  const [selected, setSelected] = useState<string>();
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [memory, setMemory] = useState<SeriesMemory>();
  const [budget, setBudget] = useState<{ spentUsd: number; limitUsd: number }>();
  const [tab, setTab] = useState<"bubbles" | "memory" | "metrics">("bubbles");
  const [fontReady, setFontReady] = useState(0);
  const [busyChapter, setBusyChapter] = useState(false);
  const [inpaintOn, setInpaintOn] = useState(true);
  const [patches, setPatches] = useState<Record<string, Record<string, PatchImage>>>({});
  const [inpaintInfo, setInpaintInfo] = useState<Record<string, string>>({});
  // Bold display lettering (title logos, brush-stroke names) stays art; its marker opens the translation.
  const [keptArt, setKeptArt] = useState<Record<string, string[]>>({});
  // Translate the next pages ahead of the reader. Opt-in: it spends credits on pages not opened yet.
  const [prefetchOn, setPrefetchOn] = useState(false);
  const [psMode, setPsMode] = useState<PsMode>("subtle");
  const requested = useRef(new Set<string>());
  const inflight = useRef(new Set<string>());

  const page = pages.find((p) => p.id === pageId);
  const state: PageState = states[pageId] ?? { regions: [], translations: {}, status: "idle" };
  const patch = useCallback((id: string, f: (s: PageState) => PageState) => {
    setStates((all) => ({ ...all, [id]: f(all[id] ?? { regions: [], translations: {}, status: "idle" }) }));
  }, []);

  useEffect(() => {
    void api.pages().then((p) => {
      setPages(p);
      setPageId((cur) => cur || p[1]?.id || p[0]?.id || "");
    });
    void api.models().then((m) => {
      setModels(m.models);
      setModel(m.default);
    });
    void api.budget().then(setBudget);
    const font = new FontFace(LETTERING_FONT, "url(/fonts/PatrickHand-Regular.ttf)");
    void font.load().then((f) => {
      document.fonts.add(f);
      setFontReady((n) => n + 1);
    });
  }, []);

  // Load cached result (text + geometry only) and the series memory when the page/model changes.
  useEffect(() => {
    if (!page || !model) return;
    setSelected(undefined);
    setEdits({});
    void api.memory(page.seriesId, NS, page.title).then(setMemory);
    if (states[page.id]?.status === "translating" || states[page.id]?.status === "detecting") return;
    void api.cached(page.id, model, NS).then(({ result, ms }) => {
      if (result) patch(page.id, () => ({ regions: result.regions, translations: result.translations, result, status: "cached", cacheMs: ms }));
      else patch(page.id, () => ({ regions: [], translations: {}, status: "idle" }));
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pageId, model]);

  // Hold Space to peek at the raw page.
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.code === "Space" && !(e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement)) {
        e.preventDefault();
        setShowOriginal(true);
      }
    };
    const up = (e: KeyboardEvent) => {
      if (e.code === "Space") setShowOriginal(false);
    };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
    };
  }, []);

  const translate = useCallback(
    async (p: PageInfo) => {
      const key = `${p.id}|${model}`;
      if (inflight.current.has(key)) return; // already being translated (ahead of the reader)
      inflight.current.add(key);
      patch(p.id, () => ({ regions: [], translations: {}, status: "detecting", live: {} }));
      const t0 = performance.now();
      try {
        await translateStream({ pageId: p.id, model, ns: NS, inpaint: inpaintOn }, (e) => {
          if (e.type === "detected")
            patch(p.id, (s) => ({ ...s, regions: e.regions, status: "translating", live: { detectMs: e.detectMs } }));
          else if (e.type === "region")
            patch(p.id, (s) => ({
              ...s,
              translations: { ...s.translations, [e.t.id]: e.t },
              live: { ...s.live, firstMs: s.live?.firstMs ?? performance.now() - t0 },
            }));
          else if (e.type === "regions-added") patch(p.id, (s) => ({ ...s, regions: [...s.regions, ...e.regions] }));
          else if (e.type === "recall") patch(p.id, (s) => ({ ...s, ps: e.notes }));
          else if (e.type === "patches") {
            // Backgrounds reconstructed while the model was still translating.
            e.patches.forEach((x) => requested.current.add(`${key}|${x.id}`));
            if (e.kept?.length) setKeptArt((all) => ({ ...all, [key]: [...new Set([...(all[key] ?? []), ...e.kept!])] }));
            void loadPatchImages(e.patches).then((loaded) => {
              setPatches((all) => ({ ...all, [key]: { ...all[key], ...loaded } }));
              setInpaintInfo((m) => ({ ...m, [key]: `Đã vẽ lại nền cho ${e.patches.length} vùng ngay trong lúc dịch (${e.ms} ms, trên máy, không tốn API)` }));
            });
          }
          else if (e.type === "done") patch(p.id, (s) => ({ ...s, result: e.result, regions: e.result.regions, translations: e.result.translations, status: "done" }));
          else if (e.type === "error") patch(p.id, (s) => ({ ...s, status: "error", error: friendlyError(e.message, e.code) }));
        });
      } catch (err) {
        patch(p.id, (s) => ({ ...s, status: "error", error: String(err) }));
      } finally {
        inflight.current.delete(key);
      }
      void api.budget().then(setBudget);
      void api.memory(p.seriesId, NS, p.title).then(setMemory);
    },
    [model, patch, inpaintOn],
  );

  // Once the open page is ready, translate the next pages of the same chapter one after the
  // other (each uses the memory the previous one added), skipping pages already in the cache.
  // Prefetching is not reading: memory still only feeds a page what came before it.
  const ahead = useRef("");
  useEffect(() => {
    if (!prefetchOn || !page || !model || busyChapter || !(state.status === "done" || state.status === "cached")) return;
    const run = `${page.id}|${model}`;
    if (ahead.current === run) return;
    ahead.current = run;
    const list = pages.filter((x) => x.seriesId === page.seriesId);
    const next = list.slice(list.findIndex((x) => x.id === page.id) + 1).slice(0, PREFETCH_PAGES);
    void (async () => {
      for (const p of next) {
        if (!prefetchOn || ahead.current !== run) return; // the reader moved on: a new run starts from there
        const s = states[p.id]?.status;
        if (s === "done" || s === "detecting" || s === "translating") continue;
        const { result, ms } = await api.cached(p.id, model, NS);
        if (result) patch(p.id, () => ({ regions: result.regions, translations: result.translations, result, status: "cached", cacheMs: ms }));
        else await translate(p);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefetchOn, pageId, model, state.status, busyChapter]);

  const modelInfo = models.find((m) => m.id === model);
  const perPage = modelInfo ? estimatePageUsd(modelInfo) : undefined;

  const translateChapter = async () => {
    if (!page) return;
    setBusyChapter(true);
    for (const p of pages.filter((x) => x.seriesId === page.seriesId)) {
      setPageId(p.id);
      await translate(p);
    }
    setBusyChapter(false);
  };

  const translations = useMemo(() => {
    const out: Record<string, RegionTranslation> = {};
    for (const [id, t] of Object.entries(state.translations)) out[id] = edits[id] !== undefined ? { ...t, vi: edits[id] } : t;
    return out;
  }, [state.translations, edits]);

  const sel = selected ? { region: state.regions.find((r) => r.id === selected), t: translations[selected] } : undefined;
  const psNotes = useMemo(() => state.result?.recall?.notes ?? state.ps ?? NO_NOTES, [state.result, state.ps]);
  const selPs = selected ? psNotes.find((n) => n.regionId === selected) : undefined;
  const ordered = [...state.regions].sort((a, b) => (translations[a.id]?.seq ?? 999 + a.order) - (translations[b.id]?.seq ?? 999 + b.order));
  const series = memory;

  const patchKey = `${pageId}|${model}`;
  const requestInpaint = useCallback(
    async (ids: string[]) => {
      const key = `${pageId}|${model}`;
      const fresh = ids.filter((id) => !requested.current.has(`${key}|${id}`));
      if (!inpaintOn || !fresh.length) return;
      fresh.forEach((id) => requested.current.add(`${key}|${id}`));
      setInpaintInfo((m) => ({ ...m, [key]: `Đang vẽ lại nền tranh cho ${fresh.length} vùng (MI-GAN, trên máy)…` }));
      try {
        const res = await api.inpaint({ pageId, model, ns: NS, ids: fresh });
        const loaded = await loadPatchImages(res.patches);
        const kept = (res.rejected ?? []).filter((x) => x.reason === "bold-text").map((x) => x.id);
        if (kept.length) setKeptArt((all) => ({ ...all, [key]: [...new Set([...(all[key] ?? []), ...kept])] }));
        setPatches((all) => ({ ...all, [key]: { ...all[key], ...loaded } }));
        setInpaintInfo((m) => ({ ...m, [key]: `Đã vẽ lại nền cho ${res.patches.length} vùng trong ${res.ms} ms (trên máy, không tốn API)` }));
      } catch (e) {
        setInpaintInfo((m) => ({ ...m, [key]: `Inpaint lỗi: ${String(e)}` }));
      }
    },
    [pageId, model, inpaintOn],
  );

  const decide = async (ja: string, status: EntryStatus, vi?: string) => {
    if (!page) return;
    setMemory(await api.setEntity({ ns: NS, seriesId: page.seriesId, ja, status, vi }));
  };

  return (
    <div className="app">
      <header>
        <div className="brand">
          <strong>Live translation</strong> <span>Nhật → Việt · demo M0</span>
        </div>
        <label>
          Model{" "}
          <select value={model} onChange={(e) => setModel(e.target.value)}>
            {models.map((m) => (
              <option key={m.id} value={m.id}>
                {m.label}
                {m.inUsd ? ` · $${m.inUsd}/$${m.outUsd} per 1M` : ""}
              </option>
            ))}
          </select>
        </label>
        <button className="primary" disabled={!page || state.status === "translating" || busyChapter} onClick={() => page && translate(page)}>
          {state.status === "done" || state.status === "cached" ? "Dịch lại trang" : "Dịch trang"}
        </button>
        <button disabled={!page || busyChapter} onClick={translateChapter}>
          Dịch cả chương (tuần tự, có bộ nhớ)
        </button>
        <button className={showOriginal ? "on" : ""} onClick={() => setShowOriginal((v) => !v)} title="Hoặc giữ phím Space">
          {showOriginal ? "Đang xem bản gốc" : "Xem bản gốc"}
        </button>
        <label className="toggle">
          <input type="checkbox" checked={inpaintOn} onChange={(e) => setInpaintOn(e.target.checked)} /> Xóa chữ trên tranh (inpaint)
        </label>
        <label title="Khi một câu nhắc lại chuyện cũ, ghi chú P/S chỉ chương/trang để đọc lại. Không bao giờ đè lên tranh; “Xem bản gốc” ẩn tất cả.">
          P/S nhắc chuyện cũ{" "}
          <select value={psMode} onChange={(e) => setPsMode(e.target.value as PsMode)}>
            <option value="off">Tắt</option>
            <option value="subtle">Kín đáo (chấm bấm xem)</option>
            <option value="on">Hiện trong khe tranh</option>
          </select>
        </label>
        <label className="toggle" title="Dịch sẵn các trang kế tiếp trong lúc bạn đọc, để lật trang là có ngay. Tốn credit cho cả trang chưa mở.">
          <input type="checkbox" checked={prefetchOn} onChange={(e) => setPrefetchOn(e.target.checked)} /> Dịch trước {PREFETCH_PAGES} trang kế
          {perPage !== undefined ? ` (~$${perPage.toFixed(4)}/trang)` : ""}
        </label>
        <span className="budget">
          {budget ? `Đã dùng $${budget.spentUsd.toFixed(4)} / $${budget.limitUsd.toFixed(2)}` : ""}
        </span>
      </header>

      <aside className="pages">
        {groupBySeries(pages).map(([title, list]) => (
          <div key={title}>
            <h4>{title}</h4>
            {list.map((p) => {
              const s = states[p.id]?.status;
              return (
                <button key={p.id} className={p.id === pageId ? "page on" : "page"} onClick={() => setPageId(p.id)}>
                  {p.id} <small>tr.{p.position.page}</small>
                  {s && s !== "idle" && <span className={`dot ${s}`} />}
                </button>
              );
            })}
          </div>
        ))}
      </aside>

      <main>
        {page && (
          <Viewer
            key={page.id}
            src={api.imageUrl(page.id)}
            regions={state.regions}
            translations={translations}
            showOriginal={showOriginal}
            fontReady={fontReady}
            selected={selected}
            onSelect={setSelected}
            patches={inpaintOn ? patches[patchKey] : undefined}
            keep={keptArt[patchKey]}
            onNeedInpaint={state.status === "done" || state.status === "cached" ? requestInpaint : undefined}
            notes={psMode === "off" ? NO_NOTES : psNotes}
            psMode={psMode}
          />
        )}
        <div className={`status ${state.status}`}>
          {statusText(state)}
          {inpaintOn && inpaintInfo[patchKey] ? ` · ${inpaintInfo[patchKey]}` : ""}
        </div>
      </main>

      <section className="panel">
        <nav>
          <button className={tab === "bubbles" ? "on" : ""} onClick={() => setTab("bubbles")}>
            Bóng thoại ({Object.keys(state.translations).length}/{state.regions.length})
          </button>
          <button className={tab === "memory" ? "on" : ""} onClick={() => setTab("memory")}>
            Bộ nhớ truyện
            {series && series.entities.some((e) => e.status === "auto") ? " •" : ""}
          </button>
          <button className={tab === "metrics" ? "on" : ""} onClick={() => setTab("metrics")}>
            Số đo
          </button>
        </nav>

        {tab === "bubbles" && (
          <div className="list">
            {sel?.region && (
              <div className="inspector">
                <div className="row">
                  <b>{sel.region.id}</b> · {sel.t ? ROLE_VI[sel.t.role] : "chưa dịch"} · {sel.region.kind === "bubble" ? "trong bóng" : "chữ tự do"}
                </div>
                {sel.t && (
                  <>
                    <div className="ja">{sel.t.ja || "—"}</div>
                    <textarea
                      value={edits[sel.region.id] ?? sel.t.vi}
                      onChange={(e) => setEdits((x) => ({ ...x, [sel.region!.id]: e.target.value }))}
                    />
                    {selPs && <div className="ps-note">{selPs.text}</div>}
                    <div className="meta">
                      Người nói: {sel.t.speaker} → {sel.t.to}
                      {sel.t.style.length ? ` · ${sel.t.style.join(", ")}` : ""}
                      {sel.t.fixes.length ? ` · đã sửa tự động: ${sel.t.fixes.join(", ")}` : ""}
                    </div>
                  </>
                )}
              </div>
            )}
            {ordered.map((r) => {
              const t = translations[r.id];
              return (
                <button key={r.id} className={r.id === selected ? "item on" : "item"} onClick={() => setSelected(r.id)}>
                  <span className="id">{r.id}</span>
                  {t ? (
                    <span>
                      <span className="ja">{t.ja}</span>
                      <span className="vi">{t.vi || <i>{ROLE_VI[t.role]}</i>}</span>
                    </span>
                  ) : (
                    <span className="pending">đang chờ…</span>
                  )}
                </button>
              );
            })}
            {state.result && state.result.notes.missed.length > 0 && (
              <div className="missed">
                <b>Chữ ngoài vùng phát hiện (model báo):</b>
                {state.result.notes.missed.map((m, i) => (
                  <div key={i}>
                    {m.ja} → {m.vi}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {tab === "memory" && series && (
          <div className="list memory">
            <p className="hint">
              Chỉ gồm những gì đã đọc tới trang hiện tại. Tên AI đề xuất cần bạn xác nhận; tên đã khóa luôn được ưu tiên.
            </p>
            {series.entities.length === 0 && <p className="hint">Chưa có gì — dịch một trang để bắt đầu.</p>}
            {series.entities.map((e) => (
              <div key={e.ja} className={`entity ${e.status}`}>
                <div>
                  <b>{e.vi}</b> <span className="ja">{e.ja}</span> <small>{e.kind}</small>
                </div>
                <div className="actions">
                  <span className="badge">{statusVi(e.status)}</span>
                  {e.status === "auto" && (
                    <>
                      <button onClick={() => decide(e.ja, "confirmed")}>Đúng</button>
                      <button
                        onClick={() => {
                          const v = prompt(`Cách dịch cho ${e.ja}:`, e.vi);
                          if (v) void decide(e.ja, "locked", v);
                        }}
                      >
                        Đổi
                      </button>
                      <button onClick={() => decide(e.ja, "rejected")}>Bỏ</button>
                    </>
                  )}
                  {e.status !== "auto" && (
                    <button
                      onClick={() => {
                        const v = prompt(`Sửa cách dịch cho ${e.ja}:`, e.vi);
                        if (v) void decide(e.ja, "locked", v);
                      }}
                    >
                      Sửa
                    </button>
                  )}
                </div>
              </div>
            ))}
            {series.address.length > 0 && <h5>Xưng hô theo chiều</h5>}
            {series.address.map((a, i) => (
              <div key={i} className="addr">
                {a.from} → {a.to}: gọi “{a.call ?? "?"}” · tự xưng “{a.selfVi ?? "?"}” · gọi người kia “{a.addressVi ?? "?"}”
              </div>
            ))}
            {series.recent.length > 0 && (
              <>
                <h5>Thoại gần nhất ({series.recent.length})</h5>
                {series.recent.slice(-6).map((r, i) => (
                  <div key={i} className="recent">
                    [{r.speaker}] {r.vi}
                  </div>
                ))}
              </>
            )}
            <button
              className="danger"
              onClick={async () => {
                if (!page || !confirm("Xóa bộ nhớ của truyện này?")) return;
                await api.resetMemory({ ns: NS, seriesId: page.seriesId, title: page.title });
                setMemory(await api.memory(page.seriesId, NS, page.title));
              }}
            >
              Xóa bộ nhớ truyện
            </button>
          </div>
        )}

        {tab === "metrics" && (
          <div className="list metrics">
            {state.result ? (
              <table>
                <tbody>
                  <tr><td>Model</td><td>{state.result.model}</td></tr>
                  <tr><td>Phát hiện vùng chữ</td><td>{state.result.timings.detectMs} ms</td></tr>
                  <tr><td>Byte đầu tiên từ model</td><td>{fmt(state.result.timings.ttfbMs)}</td></tr>
                  <tr><td>Bóng đầu tiên xong</td><td>{fmt(state.result.timings.firstRegionMs)}</td></tr>
                  <tr><td>Cả trang</td><td>{fmt(state.result.timings.totalMs)}</td></tr>
                  {state.cacheMs !== undefined && <tr><td>Mở lại từ cache</td><td>{state.cacheMs.toFixed(1)} ms (máy chủ)</td></tr>}
                  <tr><td>Token vào / ra</td><td>{state.result.usage.promptTokens ?? "—"} / {state.result.usage.completionTokens ?? "—"}</td></tr>
                  <tr><td>Chi phí trang này</td><td>${(state.result.usage.costUsd ?? 0).toFixed(5)}</td></tr>
                  <tr><td>Vùng thiếu / đã sửa</td><td>{state.result.missingIds.join(", ") || "0"} / {state.result.repairedIds.join(", ") || "0"}</td></tr>
                  <tr>
                    <td>Nhắc chuyện cũ (recall)</td>
                    <td>
                      {state.result.recall
                        ? `vùng ${state.result.recall.request.regions.join(", ")} · ${state.result.recall.cards} thẻ khớp · sửa ${state.result.recall.revised.length} · P/S ${state.result.recall.notes.length} · ${fmt(state.result.recall.ms)} · $${state.result.recall.costUsd.toFixed(5)}`
                        : "không cần"}
                    </td>
                  </tr>
                </tbody>
              </table>
            ) : (
              <p className="hint">Chưa có số đo cho trang này.</p>
            )}
            <p className="hint">Số đo của một lượt chạy, không phải p95. Mỗi lượt gọi đều được ghi vào sổ chi phí riêng.</p>
          </div>
        )}
      </section>
    </div>
  );
}

function Viewer(props: {
  src: string;
  regions: TextRegion[];
  translations: Record<string, RegionTranslation>;
  showOriginal: boolean;
  fontReady: number;
  selected?: string;
  onSelect: (id?: string) => void;
  patches?: Record<string, PatchImage>;
  keep?: string[];
  onNeedInpaint?: (ids: string[]) => void;
  notes: RecallNote[];
  psMode: PsMode;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [img, setImg] = useState<HTMLImageElement>();
  const [renders, setRenders] = useState<RegionRender[]>([]);
  const [placed, setPlaced] = useState<NotePlacement[]>([]);
  const [openPs, setOpenPs] = useState<string>();
  // Gutters come from the original page pixels, once per image.
  const gutters = useRef<{ img?: HTMLImageElement; list: Gutter[] }>({ list: [] });

  useEffect(() => {
    const el = new Image();
    el.onload = () => setImg(el);
    el.src = props.src;
  }, [props.src]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !img) return;
    const frame = requestAnimationFrame(() => {
      canvas.width = img.naturalWidth;
      canvas.height = img.naturalHeight;
      const ctx = canvas.getContext("2d", { willReadFrequently: true })!;
      ctx.drawImage(img, 0, 0);
      if (props.showOriginal) {
        // "View original" restores the exact source: no lettering, no P/S.
        setRenders([]);
        setPlaced([]);
        return;
      }
      if (props.psMode === "on" && props.notes.length && gutters.current.img !== img)
        gutters.current = { img, list: findGutters(ctx.getImageData(0, 0, canvas.width, canvas.height)) };
      const rendered = renderTranslation(ctx as unknown as Ctx2D, { w: canvas.width, h: canvas.height }, props.regions, props.translations, {
        patches: props.patches,
        keep: props.keep ? new Set(props.keep) : undefined,
      });
      setRenders(rendered);
      const inputs = props.notes.flatMap((n) => {
        const r = props.regions.find((x) => x.id === n.regionId);
        return r ? [{ id: n.regionId, text: n.text, anchor: r.bubble ?? r.box }] : [];
      });
      const family = `"${LETTERING_FONT}", "Patrick Hand", sans-serif`;
      const measure = (t: string, px: number) => {
        ctx.font = `italic ${px}px ${family}`;
        return ctx.measureText(t).width;
      };
      // Subtle: dots only. On: lettered in the nearest gutter with room, else a dot.
      const notes = placeNotes(inputs, props.psMode === "on" ? gutters.current.list : [], measure, { w: canvas.width, h: canvas.height }, {
        avoid: props.regions.map((r) => r.bubble ?? r.box),
      });
      drawNotes(ctx as unknown as Ctx2D, notes, family);
      setPlaced(notes);
      const need = rendered.filter((r) => r.needsInpaint).map((r) => r.id);
      if (need.length) props.onNeedInpaint?.(need);
    });
    return () => cancelAnimationFrame(frame);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [img, props.regions, props.translations, props.showOriginal, props.fontReady, props.patches, props.keep, props.onNeedInpaint, props.notes, props.psMode]);

  const onClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const c = e.currentTarget;
    const rect = c.getBoundingClientRect();
    const x = ((e.clientX - rect.left) * c.width) / rect.width;
    const y = ((e.clientY - rect.top) * c.height) / rect.height;
    const hits = props.regions.filter((r) => {
      const b = r.bubble ?? r.box;
      return x >= b.x - 4 && x <= b.x + b.w + 4 && y >= b.y - 4 && y <= b.y + b.h + 4;
    });
    hits.sort((a, b) => a.box.w * a.box.h - b.box.w * b.box.h);
    props.onSelect(hits[0]?.id);
  };

  const w = img?.naturalWidth ?? 1;
  const h = img?.naturalHeight ?? 1;
  // SFX and title lettering stay part of the art (tap to read); text on art shows a
  // small pending dot only until its reconstructed background arrives.
  const markers = renders.filter((r) => r.status === "needs-inpaint" || r.status === "sfx" || r.status === "skipped");
  return (
    <div className="viewer">
      <div className="stage">
        <canvas ref={canvasRef} onClick={onClick} />
        {!props.showOriginal &&
          markers.map((m) => {
            const r = props.regions.find((x) => x.id === m.id);
            if (!r) return null;
            return (
              <button
                key={m.id}
                className={`marker ${m.status}`}
                style={{ left: `${(r.box.x / w) * 100}%`, top: `${(r.box.y / h) * 100}%` }}
                title={props.translations[m.id]?.vi}
                onClick={() => props.onSelect(m.id)}
              >
                {m.status === "sfx" ? "♪" : m.status === "needs-inpaint" ? "…" : "i"}
              </button>
            );
          })}
        {!props.showOriginal &&
          placed
            .filter((p) => p.mode === "dot")
            .map((p) => (
              <button
                key={`ps-${p.id}`}
                className={`marker ps${openPs === p.id ? " open" : ""}${p.box.x < w / 2 ? " left" : ""}`}
                style={{ left: `${(p.box.x / w) * 100}%`, top: `${(p.box.y / h) * 100}%` }}
                title={p.text}
                aria-label={p.text}
                onClick={() => {
                  setOpenPs((cur) => (cur === p.id ? undefined : p.id));
                  props.onSelect(p.id);
                }}
              >
                P/S
                {openPs === p.id && <span className="ps-pop">{p.text}</span>}
              </button>
            ))}
        {props.selected &&
          (() => {
            const r = props.regions.find((x) => x.id === props.selected);
            if (!r) return null;
            const b = r.bubble ?? r.box;
            return (
              <div
                className="sel"
                style={{ left: `${(b.x / w) * 100}%`, top: `${(b.y / h) * 100}%`, width: `${(b.w / w) * 100}%`, height: `${(b.h / h) * 100}%` }}
              />
            );
          })()}
      </div>
    </div>
  );
}

/** Decode reconstructed-background patches (data URLs) into drawable images. */
async function loadPatchImages(
  patches: Array<{ id: string; x: number; y: number; dataUrl: string; textBoxes?: PatchImage["textBoxes"]; textExtent?: PatchImage["textExtent"]; ink?: PatchImage["ink"]; outline?: PatchImage["outline"]; keepOut?: PatchImage["keepOut"] }>,
): Promise<Record<string, PatchImage>> {
  const loaded: Record<string, PatchImage> = {};
  await Promise.all(
    patches.map(
      (p) =>
        new Promise<void>((resolve) => {
          const im = new Image();
          im.onload = () => {
            loaded[p.id] = { x: p.x, y: p.y, image: im, textBoxes: p.textBoxes, textExtent: p.textExtent, ink: p.ink, outline: p.outline, keepOut: p.keepOut };
            resolve();
          };
          im.onerror = () => resolve();
          im.src = p.dataUrl;
        }),
    ),
  );
  return loaded;
}

const NO_NOTES: RecallNote[] = [];

const fmt = (ms?: number) => (ms === undefined ? "—" : ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(2)} s`);

function statusText(s: PageState): string {
  switch (s.status) {
    case "idle":
      return "Chưa dịch trang này. Bấm “Dịch trang”.";
    case "cached":
      return `Bản dịch đã lưu (mở lại trong ${s.cacheMs?.toFixed(1)} ms, không gọi model). Giữ Space để xem bản gốc.`;
    case "detecting":
      return "Đang tìm vùng chữ…";
    case "translating":
      return `Đang dịch… ${Object.keys(s.translations).length}/${s.regions.length} vùng${s.live?.firstMs ? ` · bóng đầu ${fmt(s.live.firstMs)}` : ""}`;
    case "done":
      return `Xong ${Object.keys(s.translations).length}/${s.regions.length} vùng · bóng đầu ${fmt(s.result?.timings.firstRegionMs)} · cả trang ${fmt(s.result?.timings.totalMs)} · $${(s.result?.usage.costUsd ?? 0).toFixed(5)}`;
    case "error":
      return `Lỗi: ${s.error}`;
  }
}

function friendlyError(message: string, code?: string): string {
  if (code === "budget") return "Đã chạm ngân sách thử nghiệm. " + message;
  if (/Key limit exceeded/i.test(message)) return "Key OpenRouter đang bị giới hạn chi tiêu (limit). Nâng limit tại openrouter.ai/settings/keys.";
  if (/429|rate-limit/i.test(message)) return "Model đang bị giới hạn tốc độ (429). Thử lại sau ít phút hoặc chọn model khác.";
  if (/401/.test(message)) return "API key không hợp lệ.";
  return message;
}

const statusVi = (s: EntryStatus) => ({ auto: "AI đề xuất", confirmed: "Đã xác nhận", locked: "Đã khóa", rejected: "Đã bỏ" })[s];

function groupBySeries(pages: PageInfo[]): Array<[string, PageInfo[]]> {
  const m = new Map<string, PageInfo[]>();
  for (const p of pages) m.set(p.title, [...(m.get(p.title) ?? []), p]);
  return [...m.entries()];
}
