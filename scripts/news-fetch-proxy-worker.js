/**
 * Cloudflare Worker that proxies news source fetches.
 *
 * Some publishers (notably SiteGround-hosted WordPress sites) serve a
 * `sgcaptcha` HTML challenge to known datacenter IPs like Render's
 * egress. Routing the fetch through a CF Worker uses Cloudflare's edge
 * IPs, which most WAFs trust, so the upstream returns the real RSS
 * body. Used opt-in via a per-source `use_proxy` flag.
 *
 * Deployment:
 *   1. https://dash.cloudflare.com → Workers & Pages → Create → Worker
 *   2. Name it e.g. `litorbit-news-fetch`
 *   3. Replace the auto-generated code with this file's contents → Deploy
 *   4. Settings → Variables and Secrets → add Secret `PROXY_SHARED_SECRET`
 *      (any random string, e.g. `openssl rand -hex 32`).
 *   5. Copy the worker URL: https://litorbit-news-fetch.<acct>.workers.dev
 *   6. On Render → litorbit-api → Environment, set:
 *        NEWS_FETCH_PROXY_BASE = <worker URL>/<PROXY_SHARED_SECRET value>
 *      i.e. embed the secret as the FIRST path segment, matching the
 *      Gemini-proxy pattern.
 *   7. To allow a new news source domain, add it to ALLOWED_HOSTS below
 *      and redeploy.
 *
 * Usage from the backend:
 *   GET <NEWS_FETCH_PROXY_BASE>?url=<urlencoded-target>
 *
 * Returns the upstream response body verbatim with the upstream's
 * status code and content-type. Hostname allowlist prevents the worker
 * from acting as an open relay.
 */

const ALLOWED_HOSTS = [
  "wattclarity.com.au",
  "www.wattclarity.com.au",
];

const BROWSER_HEADERS = {
  "User-Agent":
    "Mozilla/5.0 (X11; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0",
  Accept: "application/rss+xml, application/xml, text/xml, text/html, */*",
  "Accept-Language": "en-US,en;q=0.9",
};

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const expected = env.PROXY_SHARED_SECRET;

    // Path-prefix auth: first path segment must equal PROXY_SHARED_SECRET.
    if (expected) {
      const parts = url.pathname.split("/");
      const provided = parts[1] || "";
      if (provided !== expected) {
        return new Response(
          JSON.stringify({ error: "forbidden", reason: "bad path secret" }),
          { status: 403, headers: { "content-type": "application/json" } },
        );
      }
    }

    const target = url.searchParams.get("url");
    if (!target) {
      return new Response(
        JSON.stringify({ error: "bad_request", reason: "missing url param" }),
        { status: 400, headers: { "content-type": "application/json" } },
      );
    }

    let targetUrl;
    try {
      targetUrl = new URL(target);
    } catch {
      return new Response(
        JSON.stringify({ error: "bad_request", reason: "invalid url" }),
        { status: 400, headers: { "content-type": "application/json" } },
      );
    }

    if (!["http:", "https:"].includes(targetUrl.protocol)) {
      return new Response(
        JSON.stringify({ error: "bad_request", reason: "unsupported scheme" }),
        { status: 400, headers: { "content-type": "application/json" } },
      );
    }

    if (!ALLOWED_HOSTS.includes(targetUrl.hostname)) {
      return new Response(
        JSON.stringify({
          error: "forbidden",
          reason: "host not in allowlist",
          host: targetUrl.hostname,
        }),
        { status: 403, headers: { "content-type": "application/json" } },
      );
    }

    const upstream = await fetch(targetUrl.toString(), {
      method: "GET",
      headers: BROWSER_HEADERS,
      redirect: "follow",
    });

    // Pass through body, status, and content-type. Expose the upstream's
    // final URL (after redirects) so the backend can surface it as a
    // diagnostic in the admin UI.
    return new Response(upstream.body, {
      status: upstream.status,
      headers: {
        "content-type":
          upstream.headers.get("content-type") || "application/octet-stream",
        "x-upstream-final-url": upstream.url || targetUrl.toString(),
      },
    });
  },
};
