"""Markovian engine helpers (Meterless engines/markovian, AGENTS.md sections 2-4).

Each investigator attempt is one bounded step ("chunk"). Instead of resending
the growing chat, the next step gets only the original task plus a compact
carryover in the spec's canonical block:

    COMPLETED: <what was done>
    REMAINING: <what is left>
    DECISIONS: <key choices made>
    CONTEXT: <entities, constraints needed to continue>
"""

import math

CARRYOVER_TOKENS = 800  # spec default carryover budget
KEEP_LAST = 5           # keep only the latest items of each list so the state stays bounded


def estimate_tokens(text):
    """Spec's token estimate: ceil(chars / 4)."""
    return math.ceil(len(text) / 4)


def _evidence_label(ev):
    if ev["type"] == "log_line":
        return f"line {ev['line']}"
    return ev["id"]


def remaining_checks(verdict, root_line, retrieved_ids):
    """Fixed checklist: what the next attempt still has to do."""
    checks = []
    cited = {_evidence_label(ev) for c in verdict["kept"] for ev in c["evidence"]}
    if root_line is not None and f"line {root_line}" not in cited:
        checks.append(f"cite the root cause line {root_line}")
    for ki in retrieved_ids:
        if ki not in cited:
            checks.append(f"cite matched known issue {ki}")
    if verdict["rejected"]:
        checks.append("fix or drop the claims the critic rejected")
    return checks


def carryover_block(carryover, budget_tokens=CARRYOVER_TOKENS):
    """Render the carryover dict as the spec's COMPLETED/REMAINING/DECISIONS/CONTEXT block."""
    def items(key):
        return carryover.get(key, [])[-KEEP_LAST:]

    verified = [_evidence_label(ev) for ev in items("evidence")]
    completed = "; ".join(
        [f"claim kept: {h}" for h in items("hypotheses_alive")]
        + ([f"evidence verified by critic: {', '.join(verified)}"] if verified else [])
    ) or "nothing verified yet"
    remaining = "; ".join(items("remaining_checks")) or "none"
    decisions = "; ".join(
        [f"rejected claim: {h}" for h in items("hypotheses_killed")]
        + [f"critic: {p}" for p in items("critic_rejections")]
    ) or "none"
    context = ("suspected mods (hint only, not evidence): "
               + (", ".join(items("suspected_mods")) or "none"))

    block = (f"COMPLETED: {completed}\n"
             f"REMAINING: {remaining}\n"
             f"DECISIONS: {decisions}\n"
             f"CONTEXT: {context}")

    # Spec's absolute fallback: cut to the carryover budget.
    max_chars = budget_tokens * 4
    if len(block) > max_chars:
        block = block[:max_chars]
    return block


def run_stats(prompt_tokens, reply_tokens, feedback_tokens, max_steps, status):
    """Markovian run record for the trace.

    One entry per attempt in each list (feedback_tokens[0] is 0).
    Markovian step k costs: its own prompt (task + carryover + feedback) + its reply.
    A plain retry chat at step k would resend the first prompt, every earlier
    reply and every feedback turn so far, then generate its reply.
    """
    used = sum(prompt_tokens) + sum(reply_tokens)
    naive = 0
    for k in range(len(prompt_tokens)):
        naive += (prompt_tokens[0] + sum(reply_tokens[:k])
                  + sum(feedback_tokens[1:k + 1]) + reply_tokens[k])
    saved = naive - used
    return {
        "chunk_config": {"max_chunks": max_steps, "carryover_tokens": CARRYOVER_TOKENS},
        "chunks": len(prompt_tokens),
        "total_tokens_used": used,
        "naive_chat_tokens": naive,
        "total_tokens_saved": saved,
        "efficiency_percent": round(100 * saved / naive, 1) if naive else 0.0,
        "status": status,
    }