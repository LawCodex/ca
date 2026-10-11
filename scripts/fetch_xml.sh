#!/bin/sh
# Fetch (or refresh) the official Justice Canada consolidated-law XML repository.
# Usage: scripts/fetch_xml.sh [raw-dir]   (default: ../_raw/ca relative to the repo)
set -eu
RAW="${1:-$(cd "$(dirname "$0")/../.." && pwd)/_raw/ca}"
mkdir -p "$RAW"
if [ -d "$RAW/laws-lois-xml/.git" ]; then
  git -C "$RAW/laws-lois-xml" fetch --depth 1 origin main
  git -C "$RAW/laws-lois-xml" reset --hard origin/main
else
  git clone --depth 1 https://github.com/justicecanada/laws-lois-xml.git "$RAW/laws-lois-xml"
fi
