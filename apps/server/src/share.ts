import { randomBytes } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import type { Context, Next } from "hono";
import { getCookie } from "hono/cookie";
import { PRIVATE_DIR } from "./env";

/**
 * Share mode (SHARE_MODE=1): friends test the reader through a tunnel to this machine.
 * - Every API call needs an invite (cookie set by POST /api/invite); each invite has a daily page quota.
 * - Only the reader's own uploads are reachable: no dataset pages, labels, judge page or eval routes.
 * - Story memory and cached results live in a namespace per invite ("share-<code>").
 * - Only the default and the fast model; the server-wide budget guard (BUDGET_USD) still applies.
 * Invites: .private/share/invites.json, made with `npm run share:invite`. Usage counts (no content): usage.json.
 */
export const SHARE = process.env.SHARE_MODE === "1";
const DIR = join(PRIVATE_DIR, "share");
export const COOKIE = "lt_invite";

export interface Invite {
  code: string;
  name: string;
  dailyPages: number;
}

let invites: Invite[] | undefined;
let usage: Record<string, { day: string; pages: number }> | undefined;

export async function loadInvites(): Promise<Invite[]> {
  invites ??= JSON.parse(await readFile(join(DIR, "invites.json"), "utf8").catch(() => "[]")) as Invite[];
  return invites;
}

export async function createInvite(name: string, dailyPages: number): Promise<Invite> {
  const all = await loadInvites();
  const inv = { code: randomBytes(6).toString("base64url"), name, dailyPages };
  all.push(inv);
  await mkdir(DIR, { recursive: true });
  await writeFile(join(DIR, "invites.json"), JSON.stringify(all, null, 1), "utf8");
  return inv;
}

export async function inviteFor(code: string | undefined): Promise<Invite | undefined> {
  if (!code) return undefined;
  return (await loadInvites()).find((i) => i.code === code);
}

const today = () => new Date().toISOString().slice(0, 10);

async function loadUsage() {
  usage ??= JSON.parse(await readFile(join(DIR, "usage.json"), "utf8").catch(() => "{}"));
  return usage!;
}

export async function pagesLeft(inv: Invite): Promise<number> {
  const u = (await loadUsage())[inv.code];
  return inv.dailyPages - (u?.day === today() ? u.pages : 0);
}

/** Count one translated page against the invite's daily quota (cached pages are free). */
export async function countPage(inv: Invite): Promise<void> {
  const all = await loadUsage();
  const u = all[inv.code]?.day === today() ? all[inv.code] : { day: today(), pages: 0 };
  all[inv.code] = { ...u, pages: u.pages + 1 };
  await mkdir(DIR, { recursive: true });
  await writeFile(join(DIR, "usage.json"), JSON.stringify(all), "utf8");
}

/** Routes a share-mode visitor may use; everything else is 404. */
const OPEN = [/^\/$/, /^\/app\.(js|css)(\.map)?$/, /^\/fonts\//, /^\/api\/health$/, /^\/api\/invite$/];
const ALLOWED = [
  /^\/api\/models$/,
  /^\/api\/budget$/,
  /^\/api\/pages$/,
  /^\/api\/pages\/up:[\w]+\/image$/,
  /^\/api\/upload$/,
  /^\/api\/translate$/,
  /^\/api\/inpaint$/,
  /^\/api\/result$/,
  /^\/api\/memory(\/(entity|questions|answer|reset|update))?$/,
];

export async function shareGuard(c: Context, next: Next) {
  if (!SHARE) return next();
  const path = decodeURIComponent(c.req.path);
  if (OPEN.some((r) => r.test(path))) return next();
  if (!ALLOWED.some((r) => r.test(path))) return c.notFound();
  const inv = await inviteFor(getCookie(c, COOKIE));
  if (!inv) return c.json({ error: "Cần mã mời", code: "no-invite" }, 401);
  c.set("invite" as never, inv as never);
  return next();
}

export const currentInvite = (c: Context): Invite | undefined => (SHARE ? (c.get("invite" as never) as Invite | undefined) : undefined);
/** Memory/results namespace: the client's choice on the team's server, one per invite in share mode. */
export const nsFor = (c: Context, given?: string) => {
  const inv = currentInvite(c);
  return inv ? `share-${inv.code}` : (given ?? "demo");
};
