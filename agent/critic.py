"""Critic layer 1: plain code, no LLM.

Checks every claim in the investigator's result against the actual log
and the known issues retrieved this run. Claims with bad evidence are
rejected, and the reasons become feedback for the next retry.
"""


def normalise(text):
    """Collapse all whitespace (tabs, double spaces) so log04/05 tabs
    don't cause false rejections."""
    return " ".join(text.split())


def find_quote(lines_by_no, quote):
    """Return the first line number that contains the quote, or None.
    Used to tell the model where its quote actually is."""
    for n, line in lines_by_no.items():
        if quote in normalise(line):
            return n
    return None


def check_evidence(ev, lines_by_no, retrieved_ids):
    """Return a list of problems with one evidence item (empty = OK)."""
    problems = []

    if ev["type"] == "log_line":
        n = ev["line"]
        quote = normalise(ev["quote"])

        if n not in lines_by_no:
            problems.append(f"line {n} does not exist (log has {len(lines_by_no)} lines)")
        elif quote not in normalise(lines_by_no[n]):
            actual = find_quote(lines_by_no, quote)
            if actual is not None:
                problems.append(f"quote is on line {actual}, not line {n}")
            else:
                problems.append(f"quote does not appear on line {n} or anywhere in the log")

    elif ev["type"] == "known_issue":
        if ev["id"] not in retrieved_ids:
            problems.append(f'known issue "{ev["id"]}" was not retrieved this run')

    return problems


def check(result, numbered, retrieved_ids=()):
    """Run layer 1 on an investigator result.

    result: dict from parse_reply
    numbered: output of number_lines
    retrieved_ids: ids of known issues retrieved this run

    Returns {"kept": [claims], "rejected": [{"claim", "problems"}],
             "feedback": str, "passed": bool}
    """
    lines_by_no = dict(numbered)
    retrieved_ids = set(retrieved_ids)

    kept = []
    rejected = []

    for i, claim in enumerate(result["claims"], 1):
        problems = []

        if not claim["evidence"]:
            problems.append("no evidence cited")

        for j, ev in enumerate(claim["evidence"], 1):
            for p in check_evidence(ev, lines_by_no, retrieved_ids):
                problems.append(f"evidence {j}: {p}")

        # Strict: one bad citation rejects the whole claim.
        if problems:
            rejected.append({"claim": claim, "problems": problems})
        else:
            kept.append(claim)

    # Feedback text for the retry, one line per problem.
    feedback_lines = []
    for r in rejected:
        for p in r["problems"]:
            feedback_lines.append(f'Claim "{r["claim"]["text"]}": {p}')
    feedback = "\n".join(feedback_lines)

    return {
        "kept": kept,
        "rejected": rejected,
        "feedback": feedback,
        "passed": not rejected,
    }