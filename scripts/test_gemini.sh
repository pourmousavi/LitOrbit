#!/usr/bin/env bash
# Sanity-test the Gemini API key directly. Bypasses Render entirely so we
# can tell whether the geo-block is about the key or about Render's egress.
# Usage:  GKEY=AIza... ./scripts/test_gemini.sh
set -euo pipefail

if [[ -z "${GKEY:-}" ]]; then
  echo "Set GKEY env var first, e.g.:" >&2
  echo "  GKEY=AIza... ./scripts/test_gemini.sh" >&2
  exit 1
fi

curl -s -X POST \
  -H "Content-Type: application/json" \
  -H "x-goog-api-key: ${GKEY}" \
  "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent" \
  -d '{"contents":[{"parts":[{"text":"say hi"}]}]}'
echo
