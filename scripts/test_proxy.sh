#!/usr/bin/env bash
# Test the CF Worker proxy directly. Bypasses Render and the python SDK so
# we can isolate whether the worker forwards Gemini calls correctly.
# Usage:  GKEY=AIza... PROXY=https://litorbit-gemini-proxy.alipourmousavi.workers.dev ./scripts/test_proxy.sh
set -euo pipefail

if [[ -z "${GKEY:-}" || -z "${PROXY:-}" ]]; then
  echo "Set GKEY and PROXY env vars first, e.g.:" >&2
  echo "  GKEY=AIza... PROXY=https://...workers.dev ./scripts/test_proxy.sh" >&2
  exit 1
fi

# PROXY may already include the secret path segment, e.g.
#   https://worker.dev/abc123
# If you also set PROXY_SECRET, we'll append it as the path segment.
URL="${PROXY%/}"
if [[ -n "${PROXY_SECRET:-}" ]]; then
  URL="${URL}/${PROXY_SECRET}"
fi

curl -s -X POST \
  -H "Content-Type: application/json" \
  -H "x-goog-api-key: ${GKEY}" \
  "${URL}/v1beta/models/gemini-2.5-flash:generateContent" \
  -d '{"contents":[{"parts":[{"text":"say hi"}]}]}'
echo
