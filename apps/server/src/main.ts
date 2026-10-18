import { serve } from "@hono/node-server";
import { app } from "./app";
import { env } from "./env";
import { loadDetector } from "./detector";

serve({ fetch: app.fetch, port: env.port, hostname: "127.0.0.1" }, (info) => {
  console.log(`Live translation dev server on http://127.0.0.1:${info.port}`);
  const t0 = performance.now();
  loadDetector()
    .then(() => console.log(`Detector warm in ${Math.round(performance.now() - t0)} ms`))
    .catch((e) => console.error("Detector failed to load:", e.message));
});
