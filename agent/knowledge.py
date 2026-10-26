"""Known-issue search.

The issues live in Zetaris (fetched over REST each run). Matching happens
here in Python: an issue matches when its log signature appears in the log.
SQL LIKE can't do this directly, because the search text is the log itself,
not a column.
"""

import csv

# Fields passed to the investigator. Leaves out aliases/loader/etc. to keep
# the prompt short.
PROMPT_FIELDS = ("id", "name", "cause", "fix", "source_url")

# The view registered in Zetaris (see docs/zetaris_setup.sql).
ISSUES_SQL = ("SELECT id, name, signature, cause, fix, source_url "
              "FROM mccrash.known_issues_table")


def fetch_issues():
    """Fetch every known issue from Zetaris over REST, as a list of dicts.
    Raises ZetarisError if Zetaris is down or the query fails."""
    # Imported here so the tests (which use the CSV) don't need Zetaris.
    from agent.zetaris import rows, run_sql
    return rows(run_sql(ISSUES_SQL))


def normalise(text):
    """Collapse whitespace and ignore case, so tabs (log04/05) and spacing
    differences don't stop a match."""
    return " ".join(text.split()).lower()


def load_issues_csv(path="data/known_issues.csv"):
    """Read the issues from the CSV. Used by tests; the real run fetches
    them from Zetaris so Zetaris stays the source of truth."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [{k.strip(): (v or "").strip() for k, v in row.items()}
                for row in csv.DictReader(f)]


def match_issues(numbered, issues):
    """Return the issues whose signature appears in the log.

    numbered: output of number_lines
    issues: list of dicts with at least "id" and "signature"

    Each match is the issue's PROMPT_FIELDS plus "matched_line": the first
    line the signature was found on, so the investigator can cite both.
    """
    lines = [(n, normalise(line)) for n, line in numbered]
    matches = []

    for issue in issues:
        sig = normalise(issue.get("signature", ""))
        if not sig:
            continue
        for n, line in lines:
            if sig in line:
                match = {k: issue.get(k, "") for k in PROMPT_FIELDS}
                match["matched_line"] = n
                matches.append(match)
                break

    return matches