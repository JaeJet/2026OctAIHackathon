"""Investigator: turns a parser excerpt into a JSON diagnosis via Nemotron.

This file only guarantees the reply is well-formed JSON of the right shape.
Whether the claims are actually supported is the critic's job.
"""

import json

from agent.llm import ask
from agent.markovian import carryover_block
from agent.parser import excerpt, root_cause


class InvestigatorError(Exception):
    """The model's reply was not valid JSON of the expected shape."""


CONFIDENCE = {"high", "medium", "low"}
STATUS = {"diagnosed", "unclear"}

SYSTEM_PROMPT = """You are a Minecraft server crash investigator. You read a numbered excerpt
of a Java Edition crash report and explain what caused the crash.

Rules:
1. Every claim must cite evidence: a log line from the EXCERPT, or a known
   issue from KNOWN ISSUES.
2. For a log_line, "line" is the number before the colon. "quote" is a short
   piece of text copied exactly from after the colon on that one line.
   Do not use "...", and do not change or join lines.
3. Only cite known issue ids listed in KNOWN ISSUES. If none are listed,
   cite only log lines. Every listed known issue was matched in this log:
   add {"type": "known_issue", "id": ...} to the evidence of the claim it
   supports, next to the log line.
4. "Suspected Mods" is a hint, not evidence. Never use it as proof.
5. If the evidence does not point to a specific cause, set status to
   "unclear", keep confidence "low", and use "fix" to say what the admin
   should check next. An honest "unclear" is better than a guess.
6. If CRITIC FEEDBACK is given, fix exactly those problems.
7. Name the mod responsible in plain words (e.g. "rctmod") when a log line
   shows it, and cite that line.
8. "fix" must be something a server admin can do: update, remove or
   reconfigure a mod, change server settings, or report the bug to the mod
   author. Never suggest editing a mod's source code.
9. Reply with ONE JSON object only. No markdown, no text before or after.


Format:
{"summary": str,
 "confidence": "high" | "medium" | "low",
 "status": "diagnosed" | "unclear",
 "claims": [{"text": str,
             "evidence": [{"type": "log_line", "line": int, "quote": str}
                          | {"type": "known_issue", "id": str}]}],
 "fix": str}"""


def build_messages(numbered, found, known_issues=None, carryover=None, feedback=None):
    """Build the chat messages for one investigator call.

    numbered: output of number_lines
    found: output of find_exceptions
    known_issues: list of dicts retrieved this run (step 5), or None
    carryover: Markovian carryover dict (step 6), or None
    feedback: critic / parse feedback text from the previous attempt, or None
    """
    root = root_cause(found)

    # Root cause line number, and the excerpt around it.
    if root is None:
        root_text = "(none found)"
        # No exception found (e.g. watchdog logs): show the first 40 lines.
        excerpt_text = excerpt(numbered, 20, radius=20)
    else:
        root_text = str(root[0])
        excerpt_text = excerpt(numbered, root[0])

    # Top exception plus every Caused by, as "n: line".
    exception_lines = []
    if found["exception"] is not None:
        n, line = found["exception"]
        exception_lines.append(f"{n}: {line}")
    for n, line in found["caused_by"]:
        exception_lines.append(f"{n}: {line}")
    exception_text = "\n".join(exception_lines) if exception_lines else "(none)"

    # Known issues: one JSON object per line, so this works whatever the
    # final column names in the Data lead's sheet turn out to be.
    if known_issues:
        known_text = "\n".join(json.dumps(ki, ensure_ascii=False) for ki in known_issues)
    else:
        known_text = "(none)"

    carryover_text = carryover_block(carryover) if carryover else "(none)"
    feedback_text = feedback if feedback else "(none)"

    user_text = (
        f"ROOT CAUSE LINE: {root_text}\n"
        f"EXCEPTION LINES:\n{exception_text}\n"
        f"EXCERPT:\n{excerpt_text}\n"
        f"KNOWN ISSUES:\n{known_text}\n"
        f"CARRYOVER:\n{carryover_text}\n"
        f"CRITIC FEEDBACK:\n{feedback_text}"
    )

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_text},
    ]


def parse_reply(text):
    """Turn the model's raw reply into a dict, checking its shape.

    Raises InvestigatorError with a message that says exactly what is wrong,
    so the loop can send it back as retry feedback.
    """
    # 1. Find the JSON object (skips ```json fences or any text around it).
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise InvestigatorError("no JSON object in reply")

    # 2. Parse it.
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError as e:
        raise InvestigatorError(f"invalid JSON: {e}")

    if not isinstance(data, dict):
        raise InvestigatorError("reply must be one JSON object")

    # 3. Top-level fields.
    for key in ("summary", "fix"):
        if not isinstance(data.get(key), str):
            raise InvestigatorError(f'"{key}" must be a string')
    if data.get("confidence") not in CONFIDENCE:
        raise InvestigatorError(f'"confidence" must be one of {sorted(CONFIDENCE)}')
    if data.get("status") not in STATUS:
        raise InvestigatorError(f'"status" must be one of {sorted(STATUS)}')
    if not isinstance(data.get("claims"), list):
        raise InvestigatorError('"claims" must be a list')

    # 4. Each claim.
    for i, claim in enumerate(data["claims"], 1):
        if not isinstance(claim, dict):
            raise InvestigatorError(f"claim {i}: must be an object")
        if not isinstance(claim.get("text"), str) or not claim["text"].strip():
            raise InvestigatorError(f'claim {i}: missing "text"')
        if not isinstance(claim.get("evidence"), list):
            raise InvestigatorError(f'claim {i}: "evidence" must be a list')

        # 5. Each evidence item.
        for j, ev in enumerate(claim["evidence"], 1):
            where = f"claim {i} evidence {j}"
            if not isinstance(ev, dict):
                raise InvestigatorError(f"{where}: must be an object")

            if ev.get("type") == "log_line":
                try:
                    ev["line"] = int(ev.get("line"))
                except (TypeError, ValueError):
                    raise InvestigatorError(f'{where}: "line" must be a number')
                if not isinstance(ev.get("quote"), str) or not ev["quote"].strip():
                    raise InvestigatorError(f'{where}: missing "quote"')

            elif ev.get("type") == "known_issue":
                if not isinstance(ev.get("id"), str) or not ev["id"].strip():
                    raise InvestigatorError(f'{where}: missing "id"')

            else:
                raise InvestigatorError(
                    f'{where}: "type" must be "log_line" or "known_issue"'
                )

    return data


def investigate(numbered, found, known_issues=None, carryover=None, feedback=None):
    """One investigator call. Returns (result_dict, raw_reply).

    The raw reply is returned too so the loop can save it in the trace.
    LLMError is not caught here; it rises to the loop.
    """
    messages = build_messages(numbered, found, known_issues, carryover, feedback)
    reply = ask(messages)
    try:
        return parse_reply(reply), reply
    except InvestigatorError as e:
        e.raw = reply  # so the loop can save what the model actually sent
        raise