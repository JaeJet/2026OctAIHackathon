import json

import agent.loop as loop
from agent.investigator import InvestigatorError


def load(name):
    return open(f"data/sample_logs/{name}.txt", encoding="utf-8").read()


def make_result(quote, status="diagnosed"):
    return {"summary": "s", "confidence": "high", "status": status,
            "claims": [{"text": "rctmod NPE",
                        "evidence": [{"type": "log_line", "line": 5, "quote": quote}]}],
            "fix": "update rctmod"}


GOOD = make_result("Cannot invoke")
BAD = make_result("made up text")


def fake_investigator(replies, calls):
    """Stands in for the real investigator: returns the replies in order
    and records the feedback each call received. No LLM is called."""
    def fake(numbered, found, known_issues, carryover, feedback):
        calls.append(feedback)
        reply = replies[len(calls) - 1]
        if isinstance(reply, Exception):
            raise reply
        return reply, json.dumps(reply)
    return fake


def test_good_first_try(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(loop, "investigate", fake_investigator([GOOD], calls))
    monkeypatch.setattr(loop, "RUNS_DIR", str(tmp_path))
    final, path = loop.investigate_log(load("log03"), name="log03")
    assert len(calls) == 1
    assert final["status"] == "diagnosed"
    assert len(final["claims"]) == 1


def test_bad_then_good_sends_feedback(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(loop, "investigate", fake_investigator([BAD, GOOD], calls))
    monkeypatch.setattr(loop, "RUNS_DIR", str(tmp_path))
    final, path = loop.investigate_log(load("log03"), name="log03")
    assert len(calls) == 2
    assert calls[0] is None
    assert "anywhere in the log" in calls[1]
    assert final["status"] == "diagnosed"


def test_always_bad_gives_unclear(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(loop, "investigate", fake_investigator([BAD] * 4, calls))
    monkeypatch.setattr(loop, "RUNS_DIR", str(tmp_path))
    final, path = loop.investigate_log(load("log03"), name="log03")
    assert len(calls) == 4
    assert final["status"] == "unclear"
    assert final["claims"] == []
    assert final["dropped_claims"] == ["rctmod NPE"]


def test_invalid_json_then_good(monkeypatch, tmp_path):
    calls = []
    replies = [InvestigatorError("no JSON object in reply"), GOOD]
    monkeypatch.setattr(loop, "investigate", fake_investigator(replies, calls))
    monkeypatch.setattr(loop, "RUNS_DIR", str(tmp_path))
    final, path = loop.investigate_log(load("log03"), name="log03")
    assert "no JSON object" in calls[1]
    assert final["status"] == "diagnosed"


def test_max_retries_1_means_2_attempts(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(loop, "investigate", fake_investigator([BAD] * 2, calls))
    monkeypatch.setattr(loop, "RUNS_DIR", str(tmp_path))
    final, path = loop.investigate_log(load("log03"), max_retries=1, name="log03")
    assert len(calls) == 2
    assert final["status"] == "unclear"


def test_trace_saved(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(loop, "investigate", fake_investigator([BAD, GOOD], calls))
    monkeypatch.setattr(loop, "RUNS_DIR", str(tmp_path))
    final, path = loop.investigate_log(load("log03"), name="log03")
    trace = json.load(open(path, encoding="utf-8"))
    assert len(trace["attempts"]) == 2
    assert trace["final"]["status"] == "diagnosed"
    assert trace["carryover"]["hypotheses_killed"] == ["rctmod NPE"]