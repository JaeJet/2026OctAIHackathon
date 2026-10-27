from eval import load_answer_key, score

# A final answer shaped like the real log03 run on Tue 27 Oct.
LOG03_FINAL = {
    "status": "diagnosed",
    "confidence": "high",
    "claims": [{
        "text": "PlayerState.get() returned null",
        "evidence": [
            {"type": "log_line", "line": 5, "quote": "java.lang.NullPointerException"},
            {"type": "known_issue", "id": "KI013"},
        ],
    }],
}


def test_log03_passes():
    key = load_answer_key()
    r = score(LOG03_FINAL, key["log03"], ["KI013"])
    assert r["status_ok"]
    assert r["root_cited"]
    assert r["ki_retrieved"]
    assert r["ki_cited"]
    assert r["passed"]


def test_wrong_line_fails():
    key = load_answer_key()
    final = {"status": "diagnosed", "confidence": "high", "claims": [{
        "text": "x", "evidence": [{"type": "log_line", "line": 6, "quote": "x"}]}]}
    r = score(final, key["log03"], ["KI013"])
    assert r["root_cited"] is False
    assert not r["ki_cited"]
    assert not r["passed"]


def test_log02_unclear_passes_without_root_line():
    key = load_answer_key()
    final = {"status": "unclear", "confidence": "low", "claims": []}
    r = score(final, key["log02"], ["KI008"])
    assert r["status_ok"]
    assert r["root_cited"] is None
    assert r["passed"]


def test_log02_diagnosed_fails():
    key = load_answer_key()
    final = {"status": "diagnosed", "confidence": "high", "claims": []}
    r = score(final, key["log02"], ["KI008"])
    assert not r["status_ok"]
    assert not r["passed"]