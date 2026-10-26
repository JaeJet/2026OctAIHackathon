from agent.parser import number_lines
from agent.critic import check


def load(name):
    return number_lines(open(f"data/sample_logs/{name}.txt").read())


def make_result(*claims):
    return {"summary": "s", "confidence": "high", "status": "diagnosed",
            "claims": list(claims), "fix": "f"}


def claim(evidence):
    return {"text": "rctmod NPE", "evidence": evidence}


GOOD_LINE = {"type": "log_line", "line": 5, "quote": "Cannot invoke"}


def test_good_claim_passes():
    out = check(make_result(claim([GOOD_LINE])), load("log03"))
    assert out["passed"]
    assert len(out["kept"]) == 1
    assert out["feedback"] == ""


def test_wrong_line_says_where_quote_is():
    ev = {"type": "log_line", "line": 6, "quote": "Cannot invoke"}
    out = check(make_result(claim([ev])), load("log03"))
    assert not out["passed"]
    assert "quote is on line 5, not line 6" in out["feedback"]


def test_line_does_not_exist():
    ev = {"type": "log_line", "line": 99999, "quote": "Cannot invoke"}
    out = check(make_result(claim([ev])), load("log03"))
    assert not out["passed"]
    assert "does not exist" in out["feedback"]


def test_invented_quote_rejected():
    ev = {"type": "log_line", "line": 5, "quote": "OutOfMemoryError in rctmod"}
    out = check(make_result(claim([ev])), load("log03"))
    assert not out["passed"]
    assert "anywhere in the log" in out["feedback"]


def test_no_evidence_rejected():
    out = check(make_result(claim([])), load("log03"))
    assert not out["passed"]
    assert "no evidence cited" in out["feedback"]


def test_unretrieved_known_issue_rejected():
    ev = {"type": "known_issue", "id": "KI-001"}
    out = check(make_result(claim([ev])), load("log03"))
    assert not out["passed"]
    assert "KI-001" in out["feedback"]


def test_retrieved_known_issue_passes():
    ev = {"type": "known_issue", "id": "KI-001"}
    out = check(make_result(claim([ev])), load("log03"), retrieved_ids=["KI-001"])
    assert out["passed"]


def test_extra_whitespace_in_quote_passes():
    ev = {"type": "log_line", "line": 5, "quote": "Cannot   invoke"}
    out = check(make_result(claim([ev])), load("log03"))
    assert out["passed"]


def test_one_bad_citation_rejects_whole_claim():
    bad = {"type": "log_line", "line": 5, "quote": "made up text"}
    out = check(make_result(claim([GOOD_LINE, bad])), load("log03"))
    assert not out["passed"]
    assert len(out["rejected"]) == 1


def test_mixed_claims_keeps_good_drops_bad():
    good = claim([GOOD_LINE])
    bad = claim([{"type": "log_line", "line": 5, "quote": "made up text"}])
    out = check(make_result(good, bad), load("log03"))
    assert len(out["kept"]) == 1
    assert len(out["rejected"]) == 1