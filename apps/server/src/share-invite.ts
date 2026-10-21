/**
 * Make an invite for share mode (stored in .private/share/invites.json, never committed).
 *
 *   npm run share:invite -- --name "An" [--pages 60]
 */
import { createInvite, loadInvites } from "./share";

const args = process.argv.slice(2);
const flag = (n: string, d: string) => (args.includes(`--${n}`) ? args[args.indexOf(`--${n}`) + 1] : d);
if (args.includes("--list")) {
  for (const i of await loadInvites()) console.log(`${i.code}  ${i.name}  ${i.dailyPages} trang/ngày`);
} else {
  const inv = await createInvite(flag("name", "Bạn"), Number(flag("pages", "60")));
  console.log(`Mã mời cho ${inv.name}: ${inv.code} (${inv.dailyPages} trang/ngày)`);
}
