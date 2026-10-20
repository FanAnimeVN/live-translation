/**
 * Plan pricing simulator (no API calls): which price / page allowance for the paid plans earns the
 * most while heavy readers still have a plan that lets them read freely.
 *
 *   npx tsx tools/eval/src/pricing.ts [--raw 0.5] [--wtp 1.0] [--cost 1.0]
 *
 * Every input below is an assumption to replace with beta measurements (docs/COST-PRICING.md §9):
 *   --raw   share of a reader's pages that need translating (the rest they read in Vietnamese elsewhere),
 *   --wtp   scales willingness to pay, --cost scales the cost per page,
 *   --serve keeps only plan sets that serve at least this share of heavy and binge readers (0-1).
 * Each simulated reader buys the option worth most to them (willingness to pay minus price and
 * top-ups), or stays on the free plan (BYOK / local) when nothing is worth it.
 */
const arg = (name: string, d: number) => {
  const i = process.argv.indexOf(`--${name}`);
  return i > 0 ? Number(process.argv[i + 1]) : d;
};
const RAW = arg("raw", 1);
const WTP = arg("wtp", 1);
const COST = arg("cost", 1);
const SERVE = arg("serve", 0);

/** Reading at ~20 s per page = 3 pages a minute (MangaDex estimate). */
const PAGES_PER_MIN = 3;
const personas = [
  { name: "nhẹ (15 ph × 12 ngày)", share: 0.4, minutes: 15, days: 12, wtp: 40_000, batch: 0 },
  { name: "đều (40 ph × 22 ngày)", share: 0.35, minutes: 40, days: 22, wtp: 70_000, batch: 0.15 },
  { name: "nặng (2 h × 28 ngày)", share: 0.2, minutes: 120, days: 28, wtp: 120_000, batch: 0.3 },
  { name: "cày (3 h × 30 ngày)", share: 0.05, minutes: 180, days: 30, wtp: 160_000, batch: 0.35 },
];
/** VND per page, Claude Haiku 5.5 after the output-format and caching work; batch = Message Batches (−50% on translation). */
const PAGE_LIVE = 17.7 * COST;
const PAGE_BATCH = 11.1 * COST;
/** Net of VAT 10% (prices include it) and ~3% payment fees; server share per paying reader. */
const NET = 0.882;
const INFRA = 2_000;
const TOPUP = { price: 25_000, pages: 1_000 };

interface Plan {
  name: string;
  price: number;
  pages: number;
}

function simulate(plans: Plan[], n = 20_000, seed = 7) {
  let s = seed;
  const rand = () => ((s = (s * 1103515245 + 12345) % 2147483648) / 2147483648);
  const normal = () => Math.sqrt(-2 * Math.log(rand() + 1e-12)) * Math.cos(2 * Math.PI * rand());
  let profit = 0, buyers = 0, surplus = 0, revenue = 0;
  const byPlan = new Map<string, number>();
  const seen = new Map<string, { n: number; bought: number; profit: number }>();
  for (let i = 0; i < n; i++) {
    let u = rand(), p = personas[0];
    for (const q of personas) {
      if (u < q.share) { p = q; break; }
      u -= q.share;
    }
    const pages = p.minutes * p.days * PAGES_PER_MIN * RAW;
    const wtp = p.wtp * WTP * Math.exp(0.45 * normal());
    const stat = seen.get(p.name) ?? { n: 0, bought: 0, profit: 0 };
    seen.set(p.name, stat);
    stat.n++;
    let best: { plan: Plan; pay: number; value: number } | undefined;
    for (const plan of plans) {
      const extra = Math.max(0, Math.ceil((pages - plan.pages) / TOPUP.pages));
      const pay = plan.price + extra * TOPUP.price;
      const value = wtp - pay;
      if (value >= 0 && (!best || value > best.value)) best = { plan, pay, value };
    }
    if (!best) continue;
    const cost = pages * (p.batch * PAGE_BATCH + (1 - p.batch) * PAGE_LIVE) + INFRA;
    buyers++;
    stat.bought++;
    stat.profit += best.pay * NET - cost;
    revenue += best.pay;
    profit += best.pay * NET - cost;
    surplus += best.value;
    byPlan.set(best.plan.name, (byPlan.get(best.plan.name) ?? 0) + 1);
  }
  const heavy = [...seen].filter(([k]) => k.startsWith("nặng") || k.startsWith("cày")).reduce((a, [, v]) => ({ n: a.n + v.n, bought: a.bought + v.bought }), { n: 0, bought: 0 });
  return { profitPer1000: (profit / n) * 1000, conversion: buyers / n, surplusPerBuyer: buyers ? surplus / buyers : 0, arpu: buyers ? revenue / buyers : 0, byPlan, seen, heavyServed: heavy.bought / Math.max(1, heavy.n) };
}

const fmt = (v: number) => `${Math.round(v / 1000)}k`;
const results: Array<{ plans: Plan[]; r: ReturnType<typeof simulate> }> = [];
for (const pa of [39_000, 49_000, 59_000, 69_000, 79_000])
  for (const qa of [1_000, 1_500, 2_000, 3_000, 4_000])
    for (const pb of [99_000, 129_000, 149_000, 179_000, 199_000])
      for (const qb of [5_000, 8_000, 12_000, 20_000]) {
        if (pb <= pa || qb <= qa) continue;
        const plans = [{ name: "A", price: pa, pages: qa }, { name: "B", price: pb, pages: qb }];
        results.push({ plans, r: simulate(plans) });
      }
results.sort((x, y) => y.r.profitPer1000 - x.r.profitPer1000);
// --show 49000,2000,99000,8000 prints that plan set too (after the best ones).
const show = process.argv.includes("--show") ? process.argv[process.argv.indexOf("--show") + 1].split(",").map(Number) : undefined;
const kept = results.filter((x) => x.r.heavyServed >= SERVE || (show && x.plans[0].price === show[0] && x.plans[0].pages === show[1] && x.plans[1].price === show[2] && x.plans[1].pages === show[3]));
if (show) {
  const at = kept.findIndex((x) => x.plans[0].price === show[0] && x.plans[0].pages === show[1] && x.plans[1].price === show[2] && x.plans[1].pages === show[3]);
  if (at > 4) kept.splice(4, 0, kept[at]);
}
console.log(`raw share ${RAW}, wtp ×${WTP}, cost ×${COST}; live ${PAGE_LIVE.toFixed(1)} đ/trang, batch ${PAGE_BATCH.toFixed(1)} đ/trang`);
for (const p of personas) {
  const pages = p.minutes * p.days * PAGES_PER_MIN * RAW;
  console.log(`  ${p.name.padEnd(24)} ${String(Math.round(pages)).padStart(6)} trang/tháng, giá vốn ${fmt(pages * (p.batch * PAGE_BATCH + (1 - p.batch) * PAGE_LIVE))}`);
}
console.log(`top plan pairs by profit per 1,000 potential readers${SERVE ? ` (serving ≥ ${SERVE * 100}% of heavy/binge readers)` : ""}:`);
for (const { plans, r } of kept.slice(0, 5))
  console.log(
    `  A ${fmt(plans[0].price)}/${plans[0].pages} trang + B ${fmt(plans[1].price)}/${plans[1].pages} trang → lãi ${fmt(r.profitPer1000)}/1.000 người, trả tiền ${(100 * r.conversion).toFixed(0)}%, ARPU ${fmt(r.arpu)}, nặng+cày được phục vụ ${(100 * r.heavyServed).toFixed(0)}% | ` +
      [...r.seen].map(([k, v]) => `${k.split(" ")[0]} mua ${((100 * v.bought) / v.n).toFixed(0)}% lãi/người ${fmt(v.bought ? v.profit / v.bought : 0)}`).join(", "),
  );
