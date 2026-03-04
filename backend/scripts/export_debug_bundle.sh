#!/usr/bin/env bash
# backend/scripts/export_debug_bundle.sh
#
# Export a PredictPod debug bundle for a given date.
#
# Usage:
#   ./export_debug_bundle.sh [YYYY-MM-DD] [output_dir]
#
# Examples:
#   ./export_debug_bundle.sh                    # today, current dir
#   ./export_debug_bundle.sh 2026-03-02         # specific date, current dir
#   ./export_debug_bundle.sh 2026-03-02 /tmp    # specific date, /tmp
#
# The script calls GET /api/debug/bundle?date=YYYY-MM-DD and saves the zip.

set -euo pipefail

DATE="${1:-$(date -u +%Y-%m-%d)}"
OUT_DIR="${2:-.}"
API_BASE="${API_BASE:-http://localhost:8000}"

FILENAME="debug_bundle_${DATE//-/}.zip"
OUT_PATH="${OUT_DIR}/${FILENAME}"

echo "==> Exporting debug bundle for ${DATE} …"
echo "    Endpoint : ${API_BASE}/api/debug/bundle?date=${DATE}"
echo "    Output   : ${OUT_PATH}"

HTTP_CODE=$(curl \
  --silent \
  --show-error \
  --write-out "%{http_code}" \
  --output "${OUT_PATH}" \
  "${API_BASE}/api/debug/bundle?date=${DATE}"
)

if [ "${HTTP_CODE}" -eq 200 ]; then
  SIZE=$(du -sh "${OUT_PATH}" | cut -f1)
  echo "==> Done. Bundle saved: ${OUT_PATH} (${SIZE})"
elif [ "${HTTP_CODE}" -eq 404 ]; then
  rm -f "${OUT_PATH}"
  echo "ERROR: No data found for date ${DATE} (HTTP 404)."
  exit 1
else
  rm -f "${OUT_PATH}"
  echo "ERROR: Server returned HTTP ${HTTP_CODE}."
  exit 1
fi
