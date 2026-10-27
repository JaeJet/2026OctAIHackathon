# Eval results

Run Tue 27 Oct 2026 12:06 with max_retries=1. Pass = status matches the answer key, and for a confident diagnosis the root cause line is cited.

| Log | Expected | Got | Confidence | Status OK | Root line cited | KI retrieved (Zetaris) | KI cited | Lines cited | Pass |
|---|---|---|---|---|---|---|---|---|---|
| log01 | diagnosed | diagnosed | high | yes | yes (line 23) | yes (KI014) | yes | 16, 23 | yes |
| log02 | unclear | unclear | low | yes | - (line 5) | yes (KI008) | yes | 5 | yes |
| log03 | diagnosed | diagnosed | high | yes | yes (line 5) | yes (KI013) | yes | 5, 6 | yes |
| log04 | unclear | diagnosed | high | NO | - (line 7) | yes (KI011) | yes | 7, 34 | NO |
| log05 | diagnosed | diagnosed | medium | yes | yes (line 17) | yes (KI008) | yes | 7, 17 | yes |

**4/5 passed.**
