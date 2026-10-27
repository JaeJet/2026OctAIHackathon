"""Eval: run the loop on each sample log and compare with data/answer_key.csv.

Run from the project root:
    python eval.py                 # every log in data/sample_logs that has an answer key row
    python eval.py log03 log02     # only these logs

Each log takes about 2-5 minutes (one or two Nightshift calls).
Results are printed and written to docs/eval_results.md.
Traces go to runs/<timestamp>_eval_<log>.json as usual.
"""

import csv
import json
import os
import sys
from datetime import datetime

from agent.knowledge import fetch_issues
from agent.llm import LLMError
from agent.loop import investigate_log

ANSWER_KEY = "data/answer_key.csv"
LOGS_DIR = "data/sample_logs"
RESULTS_PATH = "docs/eval_results.md"
MAX_RETRIES = 1  # 2 attempts per log: enough to recover from one bad JSON reply


def load_answer_key(path=ANSWER_KEY):
    """Return {log_name: row} from the Data lead's answer key."""
    with open(path, encoding="utf-8") as f:
        return {row["log"]: row for row in csv.DictReader(f)}


def split_ids(text):
    """'KI001; KI017' -> ['KI001', 'KI017']"""
    return [x.strip() for x in text.split(";") if x.strip()]


def score(final, row, retrieved_ids):
    """Compare one final answer with its answer key row.

    final: the dict investigate_log returns
    row: one answer key row
    retrieved_ids: KI ids matched from Zetaris for this log (from the trace)
    """
    expected_status = "diagnosed" if row["expected"] == "confident" else "unclear"
    status_ok = final["status"] == expected_status

    cited_lines, cited_ids = set(), set()
    for claim in final["claims"]:
        for ev in claim["evidence"]:
            if ev["type"] == "log_line":
                cited_lines.add(ev["line"])
            elif ev["type"] == "known_issue":
                cited_ids.add(ev["id"])

    related = split_ids(row["related_ids"])

    # The root line only has to be cited when a confident diagnosis is expected.
    if row["expected"] == "confident":
        root_cited = int(row["root_line"]) in cited_lines
    else:
        root_cited = None

    return {
        "log": row["log"],
        "expected": expected_status,
        "got": final["status"],
        "confidence": final["confidence"],
        "status_ok": status_ok,
        "root_line": row["root_line"],
        "root_cited": root_cited,
        "related_ids": related,
        "ki_retrieved": all(i in retrieved_ids for i in related),
        "ki_cited": all(i in cited_ids for i in related),
        "lines_cited": sorted(cited_lines),
        "passed": status_ok and root_cited is not False,
    }


def mark(value):
    """True/False/None -> table cell."""
    return {True: "yes", False: "NO", None: "-"}[value]


def to_markdown(results, started):
    lines = [
        "# Eval results",
        "",
        f"Run {started:%a %d %b %Y %H:%M} with max_retries={MAX_RETRIES}. "
        "Pass = status matches the answer key, and for a confident diagnosis "
        "the root cause line is cited.",
        "",
        "| Log | Expected | Got | Confidence | Status OK | Root line cited | "
        "KI retrieved (Zetaris) | KI cited | Lines cited | Pass |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        if "error" in r:
            lines.append(f"| {r['log']} | | ERROR: {r['error']} | | | | | | | NO |")
            continue
        ids = ", ".join(r["related_ids"]) or "-"
        lines.append(
            f"| {r['log']} | {r['expected']} | {r['got']} | {r['confidence']} | "
            f"{mark(r['status_ok'])} | {mark(r['root_cited'])} (line {r['root_line']}) | "
            f"{mark(r['ki_retrieved'])} ({ids}) | {mark(r['ki_cited'])} | "
            f"{', '.join(map(str, r['lines_cited'])) or '-'} | {mark(r['passed'])} |"
        )
    passed = sum(1 for r in results if r.get("passed"))
    lines += ["", f"**{passed}/{len(results)} passed.**", ""]
    return "\n".join(lines)


def main(names):
    key = load_answer_key()
    if not names:
        names = sorted(os.path.splitext(f)[0] for f in os.listdir(LOGS_DIR)
                       if f.endswith(".txt"))
    names = [n for n in names if n in key]

    started = datetime.now()
    all_issues = fetch_issues()
    print(f"Fetched {len(all_issues)} known issues from Zetaris")
    print(f"Evaluating {len(names)} logs: {', '.join(names)}\n")

    results = []
    for n in names:
        print(f"{n}: running...", flush=True)
        text = open(os.path.join(LOGS_DIR, f"{n}.txt"), encoding="utf-8").read()
        try:
            final, trace_path = investigate_log(
                text, max_retries=MAX_RETRIES, name=f"eval_{n}", all_issues=all_issues)
        except LLMError as e:
            # One slow or failed call shouldn't stop the whole eval.
            results.append({"log": n, "error": str(e).splitlines()[0]})
            print(f"{n}: ERROR {e}")
            continue
        with open(trace_path, encoding="utf-8") as f:
            retrieved_ids = json.load(f)["retrieved_ids"]
        r = score(final, key[n], retrieved_ids)
        results.append(r)
        print(f"{n}: got {r['got']} (expected {r['expected']}), "
              f"pass={mark(r['passed'])}  trace: {trace_path}")

    report = to_markdown(results, started)
    os.makedirs(os.path.dirname(RESULTS_PATH), exist_ok=True)
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        f.write(report)
    print("\n" + report)
    print(f"Saved to {RESULTS_PATH}")


if __name__ == "__main__":
    main(sys.argv[1:])