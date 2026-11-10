#!/bin/sh
# Stop the stack and pack everything needed to run it elsewhere:
#   .env + ./data  ->  family-agents-<date>.tar.gz
# Run from the stack directory. The stack stays stopped afterwards, so the
# old host can never answer Telegram or the tunnel at the same time as the new one.
set -eu
cd "$(dirname "$0")/.."
[ -f .env ] || { echo "no .env here" >&2; exit 1; }
docker compose down
out="family-agents-$(date +%Y%m%d-%H%M).tar.gz"
tar czf "$out" .env data
chmod 600 "$out"
echo "Packed $out ($(du -h "$out" | cut -f1)). It contains secrets: move it, then delete it."
