"""Demo: show the critic rejecting bad claims on log05.

No LLM call, so it runs instantly and gives the same result every time.
Run from the project root:  python tools/demo_critic.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.parser import number_lines
from agent.critic import check

numbered = number_lines(open("data/sample_logs/log05.txt", encoding="utf-8").read())

result = {
    "summary": "Watchdog shutdown caused by BattleTowers world generation.",
    "confidence": "high",
    "status": "diagnosed",
    "fix": "Update or remove BrassAmberBattleTowers.",
    "claims": [
        # 1. Real claim from the agent's answer: should be KEPT
        {"text": "BattleTowers isSpawnableChunk made the tick take too long.",
         "evidence": [{"type": "log_line", "line": 17,
                       "quote": "LandBattleTower.isSpawnableChunk(LandBattleTower.java:128)"}]},
        # 2. Right quote, wrong line number: should be REJECTED
        {"text": "The watchdog fired after a 60 second tick.",
         "evidence": [{"type": "log_line", "line": 9,
                       "quote": "a single server tick took 60.00 seconds"}]},
        # 3. Made-up quote (a typical hallucination): should be REJECTED
        {"text": "The server ran out of memory.",
         "evidence": [{"type": "log_line", "line": 17,
                       "quote": "java.lang.OutOfMemoryError: Java heap space"}]},
    ],
}

verdict = check(result, numbered, retrieved_ids=["KI008"])

print("KEPT:")
for c in verdict["kept"]:
    print("  +", c["text"])
print("\nREJECTED:")
for r in verdict["rejected"]:
    print("  -", r["claim"]["text"])
    for p in r["problems"]:
        print("      reason:", p)
print("\nFeedback sent back to the investigator:")
print(verdict["feedback"])