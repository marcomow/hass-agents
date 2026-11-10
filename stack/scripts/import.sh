#!/bin/sh
# Unpack an export on the new host and start the stack.
#   scripts/import.sh family-agents-YYYYMMDD-HHMM.tar.gz
set -eu
[ $# -eq 1 ] || { echo "usage: $0 <export.tar.gz>" >&2; exit 1; }
archive="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
cd "$(dirname "$0")/.."
if [ -e data ] && [ -n "$(ls -A data 2>/dev/null)" ]; then
  echo "./data is not empty here; refusing to overwrite" >&2; exit 1
fi
tar xzf "$archive"
docker compose up -d --build
docker compose ps
