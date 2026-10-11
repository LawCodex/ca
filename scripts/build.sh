#!/bin/sh
# Rebuild the whole corpus: fetch sources, regenerate Markdown, print counts.
# Usage: scripts/build.sh [raw-dir]
set -eu
REPO="$(cd "$(dirname "$0")/.." && pwd)"
RAW="${1:-$(cd "$REPO/.." && pwd)/_raw/ca}"
PY="${PYTHON:-python3}"
sh "$REPO/scripts/fetch_xml.sh" "$RAW"
rm -rf "$REPO/en/acts" "$REPO/en/regulations" "$REPO/fr/lois" "$REPO/fr/reglements" \
       "$REPO/en/constitution" "$REPO/fr/constitution"
"$PY" -I "$REPO/scripts/constitution.py" "$RAW/const" "$REPO"
"$PY" -I "$REPO/scripts/convert_xml.py" "$RAW/laws-lois-xml" "$REPO"
"$PY" -I "$REPO/scripts/stats.py" "$REPO"
