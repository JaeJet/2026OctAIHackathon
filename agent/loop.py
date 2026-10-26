"""Loop: investigator -> critic -> retry with feedback -> drop unsupported claims.

Run from the project root:
    python -m agent.loop data/sample_logs/log03.txt
"""

import json
import os
import sys
from datetime import datetime

from agent.critic import check
from agent.investigator import InvestigatorError, investigate
from agent.knowledge import ISSUES_SQL, fetch_issues, match_issues
from agent.llm import LLMError
from agent.parser import find_exceptions, number_lines

RUNS_DIR = "runs"


def new_carryover():
    """Markovian carryover: the bounded state passed between attempts
    instead of the full chat history. Step 6 fills in the rest."""
    return {
        "remaining_checks": [],
        "hypotheses_alive": [],
        "hypotheses_killed": [],
        "critic_rejections": [],
        "evidence": [],
        "suspected_mods": [],
    }


def update_carryover(carryover, verdict):
    """Record what the critic kept and killed this attempt."""
    carryover["hypotheses_alive"] = [c["text"] for c in verdict["kept"]]
    for r in verdict["rejected"]:
        if r["claim"]["text"] not in carryover["hypotheses_killed"]:
            carryover["hypotheses_killed"].append(r["claim"]["text"])
        carryover["critic_rejections"].extend(r["problems"])
    for c in verdict["kept"]:
        for ev in c["evidence"]:
            if ev not in carryover["evidence"]:
                carryover["evidence"].append(ev)


def finalise(result, verdict):
    """Build the final answer from the last valid attempt.
    Only claims the critic kept survive. Nothing left = unclear."""
    if result is None:
        return {
            "summary": "The investigator did not return a valid answer.",
            "confidence": "low",
            "status": "unclear",
            "claims": [],
            "fix": "Try again, or share the full crash report with the mod authors.",
            "dropped_claims": [],
        }

    final = dict(result)
    final["claims"] = verdict["kept"]
    final["dropped_claims"] = [r["claim"]["text"] for r in verdict["rejected"]]

    if not verdict["kept"]:
        final["status"] = "unclear"
        final["confidence"] = "low"
        # If the model already said unclear (e.g. log02), keep its own
        # summary and next steps. Otherwise its summary is unsupported.
        if result["status"] != "unclear":
            final["summary"] = "No claim could be backed by evidence from this log."
            final["fix"] = ("No supported diagnosis. Check the full server log "
                            "and the mods in the stack trace.")
    elif verdict["rejected"] and final["confidence"] == "high":
        # Some claims were dropped, so be less sure.
        final["confidence"] = "medium"

    return final


def save_trace(trace, name):
    os.makedirs(RUNS_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = os.path.join(RUNS_DIR, f"{stamp}_{name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(trace, f, indent=2, ensure_ascii=False)
    return path


def investigate_log(log_text, known_issues=None, max_retries=3, name="run",
                    all_issues=None):
    """Run the full loop on one crash log.

    known_issues: issues already matched to this log (tests pass these).
    all_issues: every issue fetched from Zetaris; if given, the ones whose
                signature appears in this log are matched here.

    Returns (final_answer, trace_path).
    max_retries=3 means up to 4 attempts in total.
    """
    numbered = number_lines(log_text)
    found = find_exceptions(numbered)
    if all_issues is not None:
        known_issues = match_issues(numbered, all_issues)
    known_issues = known_issues or []
    retrieved_ids = [ki.get("id") or ki.get("issue_id") for ki in known_issues]

    carryover = new_carryover()
    feedback = None
    last_result, last_verdict = None, None
    trace = {"name": name, "retrieved_ids": retrieved_ids,
             "retrieved": known_issues, "attempts": []}
    if all_issues is not None:
        trace["zetaris"] = {"sql": ISSUES_SQL, "rows_fetched": len(all_issues)}

    try:
        for attempt in range(1, max_retries + 2):
            step = {"attempt": attempt, "feedback_sent": feedback}
            trace["attempts"].append(step)

            try:
                # First attempt sends no carryover; later ones do.
                result, raw = investigate(
                    numbered, found, known_issues,
                    carryover if attempt > 1 else None, feedback,
                )
            except InvestigatorError as e:
                step["error"] = str(e)
                feedback = (f"Your last reply was rejected: {e}. "
                            "Reply with one valid JSON object in the required format.")
                continue

            verdict = check(result, numbered, retrieved_ids)
            step["raw"] = raw
            step["result"] = result
            step["verdict"] = verdict
            last_result, last_verdict = result, verdict
            # Update every attempt, so a clean first pass still records the
            # evidence that won (the visible Markovian state for the demo).
            update_carryover(carryover, verdict)

            if verdict["passed"]:
                break

            feedback = verdict["feedback"]

    except LLMError as e:
        trace["error"] = str(e)
        save_trace(trace, name)
        raise

    final = finalise(last_result, last_verdict)
    trace["carryover"] = carryover
    trace["final"] = final
    return final, save_trace(trace, name)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python -m agent.loop PATH_TO_LOG")
        sys.exit(1)
    path = sys.argv[1]
    text = open(path, encoding="utf-8").read()
    name = os.path.splitext(os.path.basename(path))[0]
    all_issues = fetch_issues()
    print(f"Fetched {len(all_issues)} known issues from Zetaris")
    final, trace_path = investigate_log(text, name=name, all_issues=all_issues)
    print(json.dumps(final, indent=2, ensure_ascii=False))
    print(f"\nTrace saved to {trace_path}")