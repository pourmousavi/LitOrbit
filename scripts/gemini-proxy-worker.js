/**
 * Cloudflare Worker that proxies the Gemini API.
 *
 * Render's egress IP is on Google's geo-restriction list, returning
 * `FAILED_PRECONDITION: User location is not supported` even for paid keys.
 * This Worker forwards requests from a Cloudflare edge POP, which Google
 * does not block, so the LitOrbit backend can keep using the official
 * google-genai SDK without any model swap.
 *
 * Deployment:
 *   1. https://dash.cloudflare.com → Workers & Pages → Create → Worker
 *   2. Name it e.g. `litorbit-gemini-proxy`
 *   3. Replace the auto-generated code with this file's contents → Deploy
 *   4. Optional but recommended: Settings → Variables → add a secret
 *      `PROXY_SHARED_SECRET` and set the same value as a Render env var
 *      so only your backend can use the worker.
 *   5. Copy the worker URL (e.g. https://litorbit-gemini-proxy.<acct>.workers.dev)
 *   6. On Render → litorbit-api → Environment, set:
 *        GEMINI_API_BASE = <worker URL, no trailing slash>
 *
 * This worker is read-only proxy: it never logs or stores request/response
 * bodies. All headers and the full URL path are forwarded as-is so the
 * google-genai SDK works without modification.
 */

const UPSTREAM = "https://generativelanguage.googleapis.com";

export default {
  async fetch(request, env) {
    // Optional shared-secret check. If PROXY_SHARED_SECRET is set on the
    // worker, the backend must send X-Proxy-Secret with the same value.
    if (env.PROXY_SHARED_SECRET) {
      const provided = request.headers.get("x-proxy-secret");
      if (provided !== env.PROXY_SHARED_SECRET) {
        return new Response("forbidden", { status: 403 });
      }
    }

    const url = new URL(request.url);
    const upstreamUrl = UPSTREAM + url.pathname + url.search;

    // Clone headers, dropping host (CF will set its own) and our shared secret
    // (so it never leaks upstream to Google).
    const headers = new Headers(request.headers);
    headers.delete("host");
    headers.delete("x-proxy-secret");

    const upstreamRequest = new Request(upstreamUrl, {
      method: request.method,
      headers,
      body: ["GET", "HEAD"].includes(request.method) ? undefined : request.body,
      // Required when forwarding a streamed body in Workers.
      duplex: "half",
    });

    return fetch(upstreamRequest);
  },
};
