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

SECRET_HEADER=()
if [[ -n "${PROXY_SECRET:-}" ]]; then
  SECRET_HEADER=(-H "X-Proxy-Secret: ${PROXY_SECRET}")
fi

curl -s -X POST \
  -H "Content-Type: application/json" \
  -H "x-goog-api-key: ${GKEY}" \
  "${SECRET_HEADER[@]}" \
  "${PROXY%/}/v1beta/models/gemini-2.5-flash:generateContent" \
  -d '{"contents":[{"parts":[{"text":"say hi"}]}]}'
echo
