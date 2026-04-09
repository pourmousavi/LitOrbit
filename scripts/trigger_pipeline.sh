#!/usr/bin/env bash
# Manually trigger the scheduled pipeline endpoint on Render.
# Usage:  PIPELINE_SECRET=xxxx ./scripts/trigger_pipeline.sh
set -euo pipefail

API_URL="${LITORBIT_API_URL:-https://litorbit-api.onrender.com}"
SECRET="${PIPELINE_SECRET:-}"

if [[ -z "$SECRET" ]]; then
  echo "Set PIPELINE_SECRET env var first, e.g.:" >&2
  echo "  PIPELINE_SECRET=xxxxxxxx ./scripts/trigger_pipeline.sh" >&2
  exit 1
fi

curl -i -X POST \
  -H "X-Pipeline-Secret: ${SECRET}" \
  "${API_URL%/}/api/v1/admin/pipeline/run-scheduled"
echo
