from agent.parser import number_lines, find_exceptions
from agent.investigator import build_messages, SYSTEM_PROMPT
from agent.investigator import parse_reply, InvestigatorError
import pytest


def load(name):
    text = open(f"data/sample_logs/{name}.txt").read()
    numbered = number_lines(text)
    return numbered, find_exceptions(numbered)


def test_build_messages_log03_root_cause():
    numbered, found = load("log03")
    msgs = build_messages(numbered, found)
    assert "ROOT CAUSE LINE: 5" in msgs[1]["content"]


def test_build_messages_log03_excerpt_has_npe():
    numbered, found = load("log03")
    msgs = build_messages(numbered, found)
    assert "5: " in msgs[1]["content"]
    assert "NullPointerException" in msgs[1]["content"]


def test_build_messages_log01_root_cause():
    numbered, found = load("log01")
    msgs = build_messages(numbered, found)
    assert "ROOT CAUSE LINE: 23" in msgs[1]["content"]


def test_build_messages_system_prompt_first():
    numbered, found = load("log03")
    msgs = build_messages(numbered, found)
    assert len(msgs) == 2
    assert msgs[0]["role"] == "system"
    assert msgs[0]["content"] == SYSTEM_PROMPT
    assert msgs[1]["role"] == "user"


def test_build_messages_empty_sections_say_none():
    numbered, found = load("log03")
    msgs = build_messages(numbered, found)
    assert "KNOWN ISSUES:\n(none)" in msgs[1]["content"]
    assert "CARRYOVER:\n(none)" in msgs[1]["content"]
    assert "CRITIC FEEDBACK:\n(none)" in msgs[1]["content"]


def test_build_messages_includes_known_issue_and_feedback():
    numbered, found = load("log03")
    issues = [{"id": "KI-001", "cause": "test cause"}]
    msgs = build_messages(numbered, found, known_issues=issues,
                          feedback="claim 1 evidence 1: missing quote")
    assert "KI-001" in msgs[1]["content"]
    assert "claim 1 evidence 1: missing quote" in msgs[1]["content"]

GOOD = ('{"summary": "x", "confidence": "high", "status": "diagnosed", '
        '"claims": [{"text": "c", "evidence": [{"type": "log_line", "line": 5, "quote": "q"}]}], '
        '"fix": "f"}')


def test_parse_reply_good():
    data = parse_reply(GOOD)
    assert data["status"] == "diagnosed"
    assert data["claims"][0]["evidence"][0]["line"] == 5


def test_parse_reply_strips_fences():
    data = parse_reply("```json\n" + GOOD + "\n```")
    assert data["summary"] == "x"


def test_parse_reply_line_string_becomes_int():
    data = parse_reply(GOOD.replace('"line": 5', '"line": "5"'))
    assert data["claims"][0]["evidence"][0]["line"] == 5


def test_parse_reply_rejects_bad_status():
    with pytest.raises(InvestigatorError):
        parse_reply(GOOD.replace('"diagnosed"', '"maybe"'))


def test_parse_reply_rejects_bad_evidence_type():
    with pytest.raises(InvestigatorError):
        parse_reply(GOOD.replace('"log_line"', '"forum_post"'))


def test_parse_reply_rejects_missing_quote():
    with pytest.raises(InvestigatorError):
        parse_reply(GOOD.replace('"quote": "q"', '"quote": ""'))


def test_parse_reply_rejects_no_json():
    with pytest.raises(InvestigatorError):
        parse_reply("Sorry, I can't help with that.")