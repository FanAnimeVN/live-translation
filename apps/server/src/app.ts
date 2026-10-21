import { Hono } from "hono";
import { stream } from "hono/streaming";
import {
  answerCast,
  castQuestions,
  mergePage,
  setEntityStatus,
  type CastAnswer,
  type CastQuestion,
  type EntryStatus,
  type PatchData,
  type ReadingPosition,
  type TextRegion,
  type TranslateEvent,
} from "@lt/core";
import { getPage, listPages, readPageImage } from "./dataset";
import { env, ROOT } from "./env";
import { spentUsd } from "./ledger";
import { loadMemory, saveMemory } from "./memoryStore";
import { DEFAULT_MODEL, MODELS } from "./models";
import { translatePage } from "./pipeline";
import { decodeImage } from "./image";
import { charSizesFor, inpaintRegions, type Rejected } from "./inpaint";
import { predictInpaint } from "@lt/render";
import type { DecodedPage } from "./image";
import { applyPlanned, bootstrapFromMetadata, planMemoryUpdate, searchSeries, UPDATE_EVERY_LINES } from "./context";
import { loadResult, saveResult } from "./results";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { PRIVATE_DIR } from "./env";
import { judge } from "./judge";
import { setCookie } from "hono/cookie";
import { COOKIE, countPage, currentInvite, inviteFor, nsFor, pagesLeft, SHARE, shareGuard } from "./share";
import { addUpload, findPage, listUploads, MAX_UPLOAD_BYTES, pageBytes } from "./uploads";

const locks = new Map<string, Promise<unknown>>();
/** Serialize work per series so memory updates never race. */
function serial<T>(key: string, fn: () => Promise<T>): Promise<T> {
  const prev = locks.get(key) ?? Promise.resolve();
  const next = prev.catch(() => {}).then(fn);
  locks.set(key, next);
  return next;
}

export const app = new Hono();
// Share mode: invite cookie, per-invite quota and namespace, only the reader's own uploads (share.ts).
app.use("*", shareGuard);
// A page that is not in the dataset (or not this reader's upload) is a 404, not a server error.
app.onError((e, c) => (/^Unknown page|Trang không còn/.test(e.message) ? c.json({ error: e.message }, 404) : c.json({ error: e.message }, 500)));
// Blind judging page for the team (local only): /judge
app.route("/", judge);

// Demo UI: static shell, esbuild bundle and the pinned OFL lettering font.
const DEMO = join(ROOT, "apps", "demo");
const TYPES: Record<string, string> = { js: "text/javascript", css: "text/css", map: "application/json", ttf: "font/ttf", html: "text/html; charset=utf-8", txt: "text/plain; charset=utf-8", json: "application/json" };
async function file(path: string) {
  try {
    return { body: await readFile(path), type: TYPES[path.split(".").pop() ?? ""] ?? "application/octet-stream" };
  } catch {
    return null;
  }
}
app.get("/", async (c) => {
  const f = await file(join(DEMO, "static", "index.html"));
  return f ? c.body(new Uint8Array(f.body), 200, { "Content-Type": f.type }) : c.text("Demo not built", 404);
});
app.get("/:asset{app\\.(js|css|js\\.map|css\\.map)}", async (c) => {
  const f = await file(join(DEMO, "dist", c.req.param("asset")));
  return f ? c.body(new Uint8Array(f.body), 200, { "Content-Type": f.type, "Cache-Control": "no-store" }) : c.notFound();
});
app.get("/fonts/:name", async (c) => {
  const name = c.req.param("name").replace(/[^a-zA-Z0-9._-]/g, "");
  const f = await file(join(DEMO, "public", "fonts", name));
  return f ? c.body(new Uint8Array(f.body), 200, { "Content-Type": f.type }) : c.notFound();
});

app.get("/api/health", (c) => c.json({ ok: true, share: SHARE }));

// Share mode: a friend enters the invite code once; it is kept in an httpOnly cookie.
app.post("/api/invite", async (c) => {
  const { code } = await c.req.json<{ code: string }>();
  const inv = await inviteFor(code?.trim());
  if (!inv) return c.json({ error: "Mã mời không đúng" }, 401);
  setCookie(c, COOKIE, inv.code, { httpOnly: true, sameSite: "Lax", path: "/", maxAge: 60 * 60 * 24 * 60, secure: c.req.header("x-forwarded-proto") === "https" });
  return c.json({ name: inv.name, pagesLeft: await pagesLeft(inv) });
});

/** Models a share-mode reader may pick: the default and the fast one. */
const SHARE_MODELS = new Set([DEFAULT_MODEL, "deepseek/deepseek-v4.1-flash-1017"]);

app.get("/api/models", (c) => c.json({ models: MODELS.filter((m) => !m.hidden && (!SHARE || SHARE_MODELS.has(m.id))), default: DEFAULT_MODEL }));

app.get("/api/budget", async (c) => {
  const inv = currentInvite(c);
  if (inv) return c.json({ share: { name: inv.name, pagesLeft: await pagesLeft(inv), dailyPages: inv.dailyPages } });
  return c.json({ spentUsd: await spentUsd(), limitUsd: env.budgetUsd });
});

// A page from the reader's own files (image body; title/chapter/index in the query). RAM only.
app.post("/api/upload", async (c) => {
  const bytes = Buffer.from(await c.req.arrayBuffer());
  if (!bytes.length || bytes.length > MAX_UPLOAD_BYTES) return c.json({ error: "Ảnh rỗng hoặc lớn hơn 12 MB" }, 413);
  const { title = "", chapter = "1", index = "1" } = c.req.query();
  try {
    const p = await addUpload(bytes, { title, chapter: Number(chapter), index: Number(index) }, currentInvite(c)?.code);
    const { gt, root, ...info } = p;
    return c.json({ ...info, gtCount: gt.length });
  } catch {
    return c.json({ error: "Không đọc được ảnh này" }, 400);
  }
});

app.get("/api/pages", async (c) => {
  const owner = currentInvite(c)?.code;
  const pages = [...(SHARE ? [] : await listPages()), ...listUploads(owner)];
  return c.json(pages.map(({ gt, root, ...p }) => ({ ...p, gtCount: gt.length })));
});

app.get("/api/pages/:id/image", async (c) => {
  const page = await findPage(c.req.param("id"), currentInvite(c)?.code, SHARE);
  const bytes = await pageBytes(page);
  return c.body(new Uint8Array(bytes), 200, { "Content-Type": "image/jpeg", "Cache-Control": "no-store" });
});

app.get("/api/pages/:id/gt", async (c) => c.json((await findPage(c.req.param("id"))).gt));

app.get("/api/result", async (c) => {
  const { pageId = "", model = DEFAULT_MODEL, ns: nsIn } = c.req.query();
  const ns = nsFor(c, nsIn);
  const t0 = performance.now();
  const r = await loadResult(ns, model, pageId);
  return c.json({ result: r, ms: performance.now() - t0 });
});

app.get("/api/memory", async (c) => {
  const { seriesId = "", ns: nsIn, title = "" } = c.req.query();
  return c.json(await loadMemory(nsFor(c, nsIn), seriesId, title));
});

app.post("/api/memory/entity", async (c) => {
  const body = await c.req.json<{ ns?: string; seriesId: string; ja: string; status: EntryStatus; vi?: string }>();
  const ns = nsFor(c, body.ns);
  const mem = await serial(`${ns}:${body.seriesId}`, async () => {
    const m = setEntityStatus(await loadMemory(ns, body.seriesId, ""), body.ja, body.status, body.vi);
    await saveMemory(ns, m);
    return m;
  });
  return c.json(mem);
});

// One-tap cast questions (core/cast.ts): the few uncertain facts that decide pronouns for a series.
app.get("/api/memory/questions", async (c) => {
  const { seriesId = "", ns: nsIn, chapter = "1", page = "1" } = c.req.query();
  const ns = nsFor(c, nsIn);
  const mem = await loadMemory(ns, seriesId, "");
  const pos = { chapter: Number(chapter), page: Number(page) };
  const lines = [...mem.recent, ...(mem.pending ?? [])];
  const questions = castQuestions(mem, pos).map((q) => ({
    ...q,
    sample: q.evidence.map((e) => lines.find((l) => l.pageId === e.pageId && l.regionId === e.regionId)).filter(Boolean),
  }));
  return c.json({ questions });
});

// The answer is locked into the memory and kept as a labelled example (text only, dev: .private/labels/):
// what the model had guessed, what the reader chose, and the lines between them. It measures how good
// the automatic guesses are and, later, improves the defaults. Nothing leaves the machine.
app.post("/api/memory/answer", async (c) => {
  const body = await c.req.json<{ ns?: string; seriesId: string; question: CastQuestion; answer: CastAnswer; pos: ReadingPosition }>();
  const ns = nsFor(c, body.ns);
  const mem = await serial(`${ns}:${body.seriesId}`, async () => {
    const before = await loadMemory(ns, body.seriesId, "");
    const m = answerCast(before, body.question, body.answer, body.pos);
    await saveMemory(ns, m);
    const names = new Set(body.question.who.map((w) => w.vi));
    const context = [...before.recent, ...(before.pending ?? [])]
      .filter((l) => names.has(l.speaker) || (l.to && names.has(l.to)))
      .slice(-8)
      .map((l) => ({ id: `${l.pageId}:${l.regionId}`, speaker: l.speaker, to: l.to, ja: l.ja, vi: l.vi }));
    const dir = join(PRIVATE_DIR, "labels");
    await mkdir(dir, { recursive: true });
    const row = { at: new Date().toISOString(), ns, seriesId: body.seriesId, pos: body.pos, question: body.question, answer: body.answer, context };
    await writeFile(join(dir, "cast-answers.jsonl"), JSON.stringify(row) + "\n", { flag: "a" });
    return m;
  });
  return c.json(mem);
});

app.post("/api/memory/reset", async (c) => {
  const { ns: nsIn, seriesId, title = "" } = await c.req.json<{ ns?: string; seriesId: string; title?: string }>();
  const ns = nsFor(c, nsIn);
  const { emptyMemory } = await import("@lt/core");
  await saveMemory(ns, emptyMemory(seriesId, title));
  return c.json({ ok: true });
});

app.post("/api/translate", async (c) => {
  const body = await c.req.json<{ pageId: string; model?: string; ns?: string; crops?: "small" | "all" | "none"; inpaint?: boolean }>();
  const model = body.model || DEFAULT_MODEL;
  const ns = nsFor(c, body.ns);
  const invite = currentInvite(c);
  if (invite && !SHARE_MODELS.has(model)) return c.json({ error: "Model này không mở cho bản thử" }, 403);
  const page = await findPage(body.pageId, invite?.code, SHARE);
  if (invite && (await pagesLeft(invite)) <= 0) return c.json({ error: "Hết lượt hôm nay", code: "quota" }, 429);
  c.header("Content-Type", "application/x-ndjson; charset=utf-8");
  c.header("Cache-Control", "no-store");
  return stream(c, async (s) => {
    const write = (e: TranslateEvent) => s.write(JSON.stringify(e) + "\n");
    const abort = new AbortController();
    s.onAbort(() => abort.abort());
    // Text on artwork needs a reconstructed background, and that needs no translation:
    // run MI-GAN locally while the model is still reading, and stream the patches.
    let speculative: Promise<void> | undefined;
    const onDetected = (decoded: DecodedPage, regions: TextRegion[]) => {
      if (body.inpaint === false) return;
      speculative = (async () => {
        const t0 = performance.now();
        // Let the page image be encoded and the model request go out first: the
        // prediction below is synchronous work that would delay the upload.
        await new Promise((r) => setTimeout(r, 300));
        const ids = predictInpaint(decoded.ctx.getImageData(0, 0, decoded.w, decoded.h), regions);
        if (!ids.length) return;
        const rejected: Rejected[] = [];
        const patches = await inpaintRegions(decoded, regions.filter((r) => ids.includes(r.id)), {}, rejected, regions);
        rememberPatches(page.id, regions, patches);
        const kept = rejected.filter((x) => x.reason === "bold-text").map((x) => x.id);
        if (!abort.signal.aborted) await write({ type: "patches", patches, ms: Math.round(performance.now() - t0), kept });
      })().catch((e) => console.error("speculative inpaint failed:", (e as Error).message));
    };
    try {
      await serial(`${ns}:${page.seriesId}`, async () => {
        const memory = await loadMemory(ns, page.seriesId, page.title);
        const result = await translatePage(
          { id: page.id, title: page.title, seriesId: page.seriesId, position: page.position, bytes: await pageBytes(page) },
          { model, memory, emit: (e) => void write(e), signal: abort.signal, crops: body.crops, onDetected },
        );
        const merged = mergePage(memory, page.id, page.position, result.notes, Object.values(result.translations));
        await saveMemory(ns, merged.memory);
        await saveResult(ns, result);
        if (invite) await countPage(invite);
        if ((merged.memory.pending?.length ?? 0) >= UPDATE_EVERY_LINES) void backgroundUpdate(ns, page.seriesId, page.title, false, model);
      });
      // Keep the stream open until the patches are out (they usually finish first).
      await speculative;
    } catch (e) {
      const err = e as { message?: string; code?: string };
      await write({ type: "error", message: err.message ?? String(e), code: err.code });
    }
  });
});

// Reconstructed backgrounds are image data: kept in this process's memory only (never on
// disk), keyed by page and region geometry, so reopening a page does not run MI-GAN again.
const patchCache = new Map<string, PatchData>();
const PATCH_CACHE_MAX = 400;
const patchKey = (pageId: string, r: TextRegion) => `${pageId}|${[r.box.x, r.box.y, r.box.w, r.box.h].map(Math.round).join(",")}`;
function rememberPatches(pageId: string, regions: TextRegion[], patches: PatchData[]) {
  for (const p of patches) {
    const r = regions.find((x) => x.id === p.id);
    if (!r) continue;
    patchCache.delete(patchKey(pageId, r));
    patchCache.set(patchKey(pageId, r), p);
    while (patchCache.size > PATCH_CACHE_MAX) patchCache.delete(patchCache.keys().next().value!);
  }
}

// Local reconstruction of art under text (MI-GAN on this machine): no API call, no cost.
app.post("/api/inpaint", async (c) => {
  const { pageId, model = DEFAULT_MODEL, ns: nsIn, ids } = await c.req.json<{ pageId: string; model?: string; ns?: string; ids: string[] }>();
  const ns = nsFor(c, nsIn);
  const page = await findPage(pageId, currentInvite(c)?.code, SHARE);
  const result = await loadResult(ns, model, pageId);
  const regions = (result?.regions ?? []).filter((r) => ids.includes(r.id));
  if (!regions.length) return c.json({ patches: [], ms: 0 });
  const t0 = performance.now();
  const cached = regions.flatMap((r) => {
    const p = patchCache.get(patchKey(pageId, r));
    return p ? [{ ...p, id: r.id }] : [];
  });
  const missing = regions.filter((r) => !cached.some((p) => p.id === r.id));
  const rejected: Rejected[] = [];
  let fresh: PatchData[] = [];
  if (missing.length) {
    const decoded = await decodeImage(await pageBytes(page));
    fresh = await inpaintRegions(decoded, missing, result ? charSizesFor(result) : {}, rejected, regions);
    rememberPatches(pageId, missing, fresh);
  }
  c.header("Cache-Control", "no-store");
  return c.json({ patches: [...cached, ...fresh], rejected, ms: Math.round(performance.now() - t0), fromMemory: cached.length });
});

// ---------------------------------------------------------------- context management

const updating = new Set<string>();
/** Summarize pending dialogue on a cheap model off the critical path, then merge under the series lock. */
/** A page read on a local model is summarized on it too: offline reading never calls the cloud. */
async function backgroundUpdate(ns: string, seriesId: string, title: string, force: boolean, readingModel?: string) {
  const key = `${ns}:${seriesId}`;
  if (updating.has(key)) return null;
  updating.add(key);
  try {
    const plan = await planMemoryUpdate(await loadMemory(ns, seriesId, title), force, readingModel?.startsWith("local/") ? readingModel : undefined);
    if (!plan) return null;
    return await serial(key, async () => {
      const fresh = applyPlanned(await loadMemory(ns, seriesId, title), plan);
      await saveMemory(ns, fresh);
      return { costUsd: plan.costUsd, ms: plan.ms, summary: fresh.summary };
    });
  } catch (e) {
    console.error("memory update failed:", (e as Error).message);
    return null;
  } finally {
    updating.delete(key);
  }
}

app.post("/api/memory/update", async (c) => {
  const { ns: nsIn, seriesId, title = "" } = await c.req.json<{ ns?: string; seriesId: string; title?: string }>();
  return c.json((await backgroundUpdate(nsFor(c, nsIn), seriesId, title, true)) ?? { skipped: true });
});

// Metadata lookup sends only the series title to AniList; the reader confirms the match.
app.get("/api/series/search", async (c) => c.json(await searchSeries(c.req.query("title") ?? "")));

app.post("/api/series/bootstrap", async (c) => {
  const { ns = "demo", seriesId, title = "", anilistId } = await c.req.json<{ ns?: string; seriesId: string; title?: string; anilistId: number }>();
  const key = `${ns}:${seriesId}`;
  const out = await serial(key, async () => {
    const res = await bootstrapFromMetadata(await loadMemory(ns, seriesId, title), anilistId);
    await saveMemory(ns, res.memory);
    return { profile: res.memory.profile, characters: res.memory.metadata?.characters.length ?? 0, costUsd: res.costUsd, ms: res.ms };
  });
  return c.json(out);
});

app.post("/api/ratings", async (c) => {
  const body = await c.req.json();
  await mkdir(PRIVATE_DIR, { recursive: true });
  const file = join(PRIVATE_DIR, "ratings.jsonl");
  await writeFile(file, JSON.stringify({ at: new Date().toISOString(), ...body }) + "\n", { flag: "a" });
  return c.json({ ok: true });
});

app.get("/api/eval/latest", async (c) => {
  try {
    return c.json(JSON.parse(await readFile(join(PRIVATE_DIR, "eval", "latest.json"), "utf8")));
  } catch {
    return c.json(null);
  }
});
