/**
 * Start the server in share mode (invites, quotas, uploads only) on PORT (default 8790), so the
 * team's own server on 8787 keeps the dataset. Expose it with a tunnel, e.g.
 *   cloudflared tunnel --url http://127.0.0.1:8790
 */
process.env.SHARE_MODE = "1";
process.env.PORT ??= "8790";
await import("./main");
export {};
