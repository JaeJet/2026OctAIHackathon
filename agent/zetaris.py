"""Minimal Zetaris REST client: send one SQL statement, get JSON back.

Check the connection from the project root:
    python -m agent.zetaris "SELECT 1 AS one"

Settings come from the project .env:
    ZETARIS_REST_URL, ZETARIS_ORG_ID, ZETARIS_API_KEY
"""

import json
import os
import sys
import urllib.error
import urllib.request
import uuid

from dotenv import load_dotenv

load_dotenv()


class ZetarisError(Exception):
    pass


def run_sql(sql, limit=1000, timeout=60):
    """Send ONE SQL statement to Zetaris and return the decoded JSON reply.

    limit caps the rows returned (1000 is plenty for 25 known issues)."""
    base = os.environ.get("ZETARIS_REST_URL")
    key = os.environ.get("ZETARIS_API_KEY")
    org = os.environ.get("ZETARIS_ORG_ID", "1")
    if not base or not key:
        raise ZetarisError("ZETARIS_REST_URL or ZETARIS_API_KEY missing from .env")

    # Body fields from the API reference (POST /sql-editor/sqls/run):
    # queryId is a fresh UUID per query, source "Generic" as in its sample.
    body = json.dumps({
        "queryId": str(uuid.uuid4()),
        "sql": sql,
        "limit": limit,
        "source": "Generic",
    }).encode("utf-8")

    req = urllib.request.Request(
        base.rstrip("/") + "/sql-editor/sqls/run",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "X-Org-ID": str(org),
            "X-Request-ID": str(uuid.uuid4()),
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:500]
        if e.code == 401:
            raise ZetarisError("Zetaris rejected the API key (401). Check ZETARIS_API_KEY in .env.") from e
        raise ZetarisError(f"Zetaris HTTP {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise ZetarisError(
            f"Can't reach Zetaris at {base}. Is Docker running, and did you "
            "'docker compose start' in ~/zetaris-platform?"
        ) from e


def rows(reply):
    """Turn Zetaris's reply into a list of dicts, one per row.

    Zetaris replies {"headers": ["id", "signature"], "data": [["KI001", "..."], ...]};
    zip pairs each header with the value in the same position.
    """
    headers = reply.get("headers", [])
    return [dict(zip(headers, values)) for values in reply.get("data", [])]


if __name__ == "__main__":
    sql = sys.argv[1] if len(sys.argv) > 1 else "SELECT 1 AS one"
    print(json.dumps(run_sql(sql), indent=2))