import json

import agent.loop as loop
from agent.markovian import carryover_block, remaining_checks, run_stats
from tests.test_loop import BAD, GOOD, fake_investigator, load


def test_block_has_spec_labels_in_order():
    carry = loop.new_carryover()
    block = carryover_block(carry)
    labels = [line.split(":")[0] for line in block.splitlines()]
    assert labels == ["COMPLETED", "REMAINING", "DECISIONS", "CONTEXT"]


def test_block_stays_bounded():
    # 50 rejected attempts must not grow the carryover past its budget.
    carry = loop.new_carryover()
    carry["hypotheses_killed"] = [f"long wrong guess number {i} " * 20 for i in range(50)]
    carry["critic_rejections"] = ["quote not found in the log " * 10] * 50
    block = carryover_block(carry)
    assert len(block) <= 800 * 4
    assert "number 49" in block      # keeps the latest
    assert "number 0 " not in block  # drops the oldest


def test_remaining_checks_lists_what_is_missing():
    verdict = {"kept": [], "rejected": [{"claim": {"text": "x"}, "problems": ["p"]}]}
    checks = remaining_checks(verdict, 5, ["KI013"])
    assert "cite the root cause line 5" in checks
    assert "cite matched known issue KI013" in checks
    assert "fix or drop the claims the critic rejected" in checks


def test_run_stats_one_step_saves_nothing():
    stats = run_stats([1000], [300], [0], 2, "completed")
    assert stats["total_tokens_used"] == 1300
    assert stats["total_tokens_saved"] == 0


def test_loop_sends_block_and_records_run(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(loop, "investigate", fake_investigator([BAD, GOOD], calls))
    monkeypatch.setattr(loop, "RUNS_DIR", str(tmp_path))
    final, path = loop.investigate_log(load("log03"), name="log03")
    trace = json.load(open(path, encoding="utf-8"))

    # Attempt 1 sends no carryover; attempt 2 sends the spec block.
    assert "carryover_sent" not in trace["attempts"][0]
    sent = trace["attempts"][1]["carryover_sent"]
    assert sent.startswith("COMPLETED:")
    assert "rejected claim: rctmod NPE" in sent
    assert "cite the root cause line 5" in sent

    # Run record, shaped after the spec's MarkovianRun.
    run = trace["markovian"]
    assert run["chunks"] == 2
    assert run["status"] == "completed"
    assert run["chunk_config"]["max_chunks"] == 4
    assert trace["carryover"]["remaining_checks"] == []