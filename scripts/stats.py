#!/usr/bin/env python3
"""Print per-category / per-status file counts for the README."""
import collections
import os
import sys

repo = sys.argv[1] if len(sys.argv) > 1 else "."
counts = collections.Counter()
for d in ("en/constitution", "en/acts", "en/regulations", "fr/constitution", "fr/lois", "fr/reglements"):
    for root, _, files in os.walk(os.path.join(repo, d)):
        for f in files:
            if not f.endswith(".md"):
                continue
            status = "unknown"
            with open(os.path.join(root, f), encoding="utf-8") as fh:
                for i, line in enumerate(fh):
                    if line.startswith("status:"):
                        status = line.split(":", 1)[1].strip()
                        break
                    if line.startswith("---") and i > 0:
                        break
            sub = os.path.relpath(root, os.path.join(repo, d)).split(os.sep)[0]
            counts[(d, sub if sub != "." else "", status)] += 1
tot = collections.Counter()
for (d, sub, st), n in sorted(counts.items()):
    print(f"{d:18} {sub:6} {st:9} {n}")
    tot[d] += n
print()
for d, n in tot.items():
    print(f"{d:18} {n}")
print("total", sum(tot.values()))
