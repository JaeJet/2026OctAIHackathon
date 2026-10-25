"""Turn a raw crash log into numbered lines, an exception chain, and excerpts.

No LLM here: everything is deterministic so it can be tested exactly.
"""
import re

# A Java exception line: dotted class name ending in Exception/Error/Throwable,
# optionally followed by ": message".  e.g. "java.lang.NullPointerException: x"
EXCEPTION_RE = re.compile(r"^([\w$]+\.)+[\w$]*(Exception|Error|Throwable)\b")

# Some logs prefix the top exception with: Exception in thread "main" ...
THREAD_PREFIX_RE = re.compile(r'^Exception in thread "[^"]*"\s+')


def number_lines(text):
    """Return [(1, line), (2, line), ...], numbered from 1 to match editors."""
    # splitlines() handles Windows \r\n, so no stray \r is left on each line.
    return list(enumerate(text.splitlines(), start=1))


def find_exceptions(numbered):
    """Return {"exception": (n, line) or None, "caused_by": [(n, line), ...]}.

    "exception" is the first exception line in the log (the top of the chain).
    "caused_by" is every "Caused by:" line, in order.
    """
    exception = None
    caused_by = []

    for n, line in numbered:
        stripped = line.lstrip()
        # Check "Caused by:" first, since those lines also contain exception names.
        if stripped.startswith("Caused by:"):
            caused_by.append((n, stripped))
        elif exception is None:
            candidate = THREAD_PREFIX_RE.sub("", stripped)
            if EXCEPTION_RE.match(candidate):
                exception = (n, stripped)

    return {"exception": exception, "caused_by": caused_by}


def root_cause(found):
    """Last "Caused by" if any, otherwise the top exception, otherwise None."""
    if found["caused_by"]:
        return found["caused_by"][-1]
    return found["exception"]


def excerpt(numbered, line_no, radius=5):
    """Return lines line_no-radius .. line_no+radius as text, e.g. '23: Caused by: ...'.

    Filters by line number rather than slicing by index, so a target near the
    start or end of the log just returns fewer lines instead of breaking.
    """
    lo, hi = line_no - radius, line_no + radius
    return "\n".join(f"{n}: {line}" for n, line in numbered if lo <= n <= hi)