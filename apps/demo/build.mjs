// Bundle the demo UI with esbuild (native binary, low memory). `--watch` rebuilds on change.
import * as esbuild from "esbuild";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const options = {
  entryPoints: [join(here, "src", "main.tsx")],
  outfile: join(here, "dist", "app.js"),
  bundle: true,
  format: "esm",
  platform: "browser",
  target: "es2022",
  jsx: "automatic",
  sourcemap: true,
  logLevel: "info",
  define: { "process.env.NODE_ENV": '"development"' },
};

if (process.argv.includes("--watch")) {
  const ctx = await esbuild.context(options);
  await ctx.watch();
} else {
  await esbuild.build(options);
}
