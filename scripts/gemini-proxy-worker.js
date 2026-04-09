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
 *   4. Settings → Variables and Secrets → add Secret `PROXY_SHARED_SECRET`
 *      (any random string, e.g. `openssl rand -hex 32`).
 *   5. Copy the worker URL: https://litorbit-gemini-proxy.<acct>.workers.dev
 *   6. On Render → litorbit-api → Environment, set:
 *        GEMINI_API_BASE = <worker URL>/<PROXY_SHARED_SECRET value>
 *      i.e. embed the secret as the FIRST path segment. The google-genai
 *      SDK doesn't reliably forward custom headers from
 *      HttpOptions(headers=...), so we authenticate via the URL path
 *      instead and the worker strips the secret prefix before forwarding.
 *
 * This worker is read-only proxy: it never logs or stores request/response
 * bodies. The secret is in the URL path; the upstream Google call always
 * goes to a clean /v1beta/... path with no leakage.
 */

const UPSTREAM = "https://generativelanguage.googleapis.com";

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const expected = env.PROXY_SHARED_SECRET;

    // Path-prefix auth: the first path segment must equal PROXY_SHARED_SECRET.
    // We split on '/' so url.pathname like "/SECRET/v1beta/models/..." becomes
    // ['', 'SECRET', 'v1beta', 'models', ...]. The remaining path is what we
    // forward upstream to Google.
    if (expected) {
      const parts = url.pathname.split("/");
      const provided = parts[1] || "";
      if (provided !== expected) {
        return new Response(
          JSON.stringify({ error: "forbidden", reason: "bad path secret" }),
          { status: 403, headers: { "content-type": "application/json" } },
        );
      }
      // Strip the secret segment from the forwarded path.
      parts.splice(1, 1);
      url.pathname = parts.join("/") || "/";
    }

    const upstreamUrl = UPSTREAM + url.pathname + url.search;

    // Clone headers, dropping host so CF sets the upstream's host correctly.
    const headers = new Headers(request.headers);
    headers.delete("host");

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
