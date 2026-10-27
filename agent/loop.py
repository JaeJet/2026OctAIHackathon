"""Loop: investigator -> critic -> retry with feedback -> drop unsupported claims.

Run from the project root:
    python -m agent.loop data/sample_logs/log03.txt
"""

import json
import os
import sys
from datetime import datetime

from agent.critic import check
from agent.investigator import InvestigatorError, build_messages, investigate
from agent.knowledge import ISSUES_SQL, fetch_issues, match_issues
from agent.llm import LLMError
from agent.markovian import (carryover_block, estimate_tokens,
                             remaining_checks, run_stats)
from agent.parser import find_exceptions, number_lines, root_cause

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
    root = root_cause(found)
    root_line = root[0] if root else None
    # Per-step token accounting for the Markovian run record.
    prompt_toks, reply_toks, feedback_toks = [], [], []
    status = "max-chunks"
    trace = {"name": name, "retrieved_ids": retrieved_ids,
             "retrieved": known_issues, "attempts": []}
    if all_issues is not None:
        trace["zetaris"] = {"sql": ISSUES_SQL, "rows_fetched": len(all_issues)}

    try:
        for attempt in range(1, max_retries + 2):
            step = {"attempt": attempt, "feedback_sent": feedback}
            trace["attempts"].append(step)

            # First attempt sends no carryover; later ones do.
            sent = carryover if attempt > 1 else None
            if sent:
                step["carryover_sent"] = carryover_block(sent)
            messages = build_messages(numbered, found, known_issues, sent, feedback)
            step["prompt_tokens"] = estimate_tokens(
                "".join(m["content"] for m in messages))
            prompt_toks.append(step["prompt_tokens"])
            feedback_toks.append(estimate_tokens(feedback or ""))

            try:
                result, raw = investigate(numbered, found, known_issues, sent, feedback)
            except InvestigatorError as e:
                step["error"] = str(e)
                step["raw"] = getattr(e, "raw", None)
                reply_toks.append(estimate_tokens(step["raw"] or ""))
                feedback = (f"Your last reply was rejected: {e}. "
                            "Reply with one valid JSON object in the required format.")
                continue

            reply_toks.append(estimate_tokens(raw))
            verdict = check(result, numbered, retrieved_ids)
            step["raw"] = raw
            step["result"] = result
            step["verdict"] = verdict
            last_result, last_verdict = result, verdict
            # Update every attempt, so a clean first pass still records the
            # evidence that won (the visible Markovian state for the demo).
            update_carryover(carryover, verdict)
            carryover["remaining_checks"] = remaining_checks(
                verdict, root_line, retrieved_ids)

            if verdict["passed"]:
                status = "completed"
                break

            feedback = verdict["feedback"]

    except LLMError as e:
        trace["error"] = str(e)
        reply_toks.extend([0] * (len(prompt_toks) - len(reply_toks)))
        trace["markovian"] = run_stats(prompt_toks, reply_toks, feedback_toks,
                                       max_retries + 1, "errored")
        save_trace(trace, name)
        raise

    final = finalise(last_result, last_verdict)
    trace["markovian"] = run_stats(prompt_toks, reply_toks, feedback_toks,
                                   max_retries + 1, status)
    trace["carryover"] = carryover
    trace["carryover_block"] = carryover_block(carryover)
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