#!/bin/sh
# Turn add-on options JSON files into the base64 lines .env expects.
#   scripts/encode-options.sh agents.json yuvomi.json >> .env
set -eu
[ $# -eq 2 ] || { echo "usage: $0 agents.json yuvomi.json" >&2; exit 1; }
for f in "$1" "$2"; do
  python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$f" || { echo "invalid JSON: $f" >&2; exit 1; }
done
printf 'AGENTS_OPTIONS_B64=%s\n' "$(base64 -w0 < "$1")"
printf 'YUVOMI_OPTIONS_B64=%s\n' "$(base64 -w0 < "$2")"
