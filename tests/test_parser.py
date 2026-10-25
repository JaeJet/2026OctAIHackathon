from agent.parser import number_lines, find_exceptions, root_cause, excerpt

LOG_DIR = "data/sample_logs"


def load(name):
    with open(f"{LOG_DIR}/{name}", encoding="utf-8", errors="replace") as f:
        return f.read()


# ── Real sample logs ──────────────────────────────

def test_log01_root_cause_line_23():
    numbered = number_lines(load("log01.txt"))  # ← match your real filename
    n, line = root_cause(find_exceptions(numbered))
    assert n == 23


def test_log03_npe_line_5():
    numbered = number_lines(load("log03.txt"))  # ← match your real filename
    n, line = root_cause(find_exceptions(numbered))
    assert n == 5
    assert "NullPointerException" in line


# ── Small inputs, no files needed ─────────────────

def test_number_lines_starts_at_one():
    assert number_lines("a\nb") == [(1, "a"), (2, "b")]


def test_number_lines_windows_endings():
    assert number_lines("a\r\nb") == [(1, "a"), (2, "b")]


def test_root_cause_prefers_last_caused_by():
    text = (
        "java.lang.RuntimeException: outer\n"
        "\tat a.b.C.run(C.java:1)\n"
        "Caused by: java.lang.IllegalStateException: middle\n"
        "\tat d.e.F.go(F.java:2)\n"
        "Caused by: java.lang.NullPointerException: inner\n"
        "\tat g.h.I.x(I.java:3)\n"
    )
    found = find_exceptions(number_lines(text))
    assert found["exception"][0] == 1
    assert [n for n, _ in found["caused_by"]] == [3, 5]
    assert root_cause(found)[0] == 5


def test_root_cause_without_caused_by_is_top_exception():
    text = "some log line\njava.lang.NullPointerException: boom\n\tat a.b.C.run(C.java:1)\n"
    n, line = root_cause(find_exceptions(number_lines(text)))
    assert n == 2


def test_root_cause_none_when_no_exception():
    assert root_cause(find_exceptions(number_lines("all fine\nnothing here"))) is None


def test_excerpt_near_start_does_not_break():
    numbered = number_lines("a\nb\nc")
    assert excerpt(numbered, 1, radius=5) == "1: a\n2: b\n3: c"


def test_excerpt_keeps_line_numbers():
    numbered = number_lines("\n".join(f"line{i}" for i in range(1, 21)))
    assert excerpt(numbered, 10, radius=1) == "9: line9\n10: line10\n11: line11"