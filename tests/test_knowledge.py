from agent.parser import number_lines
from agent.knowledge import load_issues_csv, match_issues


def load(name):
    return number_lines(open(f"data/sample_logs/{name}.txt", encoding="utf-8").read())


def matched_ids(name):
    return [m["id"] for m in match_issues(load(name), load_issues_csv())]


def test_csv_loads_all_issues():
    issues = load_issues_csv()
    assert len(issues) == 25
    assert issues[0]["id"] == "KI001"


# Expected ids come from the Data lead's answer key (related_ids column).

def test_log01_matches_entrypoint_error():
    assert "KI014" in matched_ids("log01")


def test_log02_matches_watchdog():
    assert "KI008" in matched_ids("log02")


def test_log03_matches_ticking_world():
    assert "KI013" in matched_ids("log03")


def test_log05_matches_watchdog():
    assert "KI008" in matched_ids("log05")


def test_match_has_line_and_prompt_fields():
    m = match_issues(load("log03"), load_issues_csv())[0]
    assert isinstance(m["matched_line"], int)
    assert set(m) == {"id", "name", "cause", "fix", "source_url", "matched_line"}


def test_whitespace_and_case_ignored():
    numbered = [(1, "DESCRIPTION:\tException   ticking world")]
    issues = [{"id": "X1", "signature": "Description: Exception ticking world"}]
    assert match_issues(numbered, issues)[0]["matched_line"] == 1


def test_no_match_returns_empty():
    numbered = [(1, "nothing interesting here")]
    issues = [{"id": "X1", "signature": "OutOfMemoryError"}]
    assert match_issues(numbered, issues) == []