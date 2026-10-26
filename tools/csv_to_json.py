"""Convert data/known_issues.csv to data/known_issues.json for Zetaris.

Run from the project root:
    python tools/csv_to_json.py

Zetaris reads the JSON from the repo's public raw GitHub URL as a
REST table, so re-run this and push whenever the CSV changes.
"""

import csv
import json

SRC = "data/known_issues.csv"
OUT = "data/known_issues.json"

with open(SRC, encoding="utf-8-sig", newline="") as f:
    # utf-8-sig drops the hidden BOM Excel adds to "CSV UTF-8" files,
    # which would otherwise turn the first header into "\ufeffid".
    rows = list(csv.DictReader(f))

# Keep every value a plain trimmed string so the table columns are simple.
rows = [{k.strip(): (v or "").strip() for k, v in row.items()} for row in rows]

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(rows, f, indent=2, ensure_ascii=False)

print(f"Wrote {len(rows)} issues to {OUT}")