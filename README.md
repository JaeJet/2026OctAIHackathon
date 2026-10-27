# Minecraft Crash Investigator

**Open Agent Hackathon 2026, Track 2.** Paste a Minecraft server crash log and get a diagnosis where every claim cites its evidence: an exact line from the log or a known issue stored in Zetaris. A critic checks each claim against the log and throws out anything it can't find. If nothing survives, the agent says "unclear" instead of guessing.

## What it does

Modded Minecraft servers crash often, and when they do, the owner is left with a crash log that can run to hundreds of lines. The real cause is usually in there somewhere, but it's buried among normal startup messages and long technical error traces. Our agent reads the crash log, works out what caused the crash, and explains how to fix it. Every claim it makes points to evidence: the exact line in the log, or a known issue from our Zetaris knowledge table. If the evidence isn't there, it says it isn't sure instead of guessing.

## Who it's for

Our main users are people who run modded Minecraft servers, from friends hosting a small server to admins of larger communities. It's also for modpack players whose game or server crashes and who don't know where to start. Most of these people aren't programmers, so they need a plain-English answer they can act on quickly. A cited answer also means they can trust the fix before changing their server.

## Why it matters

Facts checked 26 October 2026. Every number has its source beside it.

**Modded Minecraft is huge.**
- Minecraft is the best-selling video game of all time: 350 million copies ([Guinness World Records](https://www.guinnessworldrecords.jp/world-records/best-selling-video-game)).
- CurseForge and Modrinth list 326,987 mods and modpacks with about 135.4 billion combined downloads (snapshot 26 Oct 2026, [ModDex stats](https://moddex.gg/stats)).
- One modpack, All the Mods 10, has 22.6 million downloads and bundles around 500 mods. When a server running it crashes, any of those mods could be the cause ([CurseForge](https://www.curseforge.com/minecraft/modpacks/all-the-mods-10/files/7722629)).

**Crashes cost servers their players.** A May 2025 survey of 1,008 players and server owners ([Liquid Web](https://www.liquidweb.com/white-papers/minecraft-hosting-study/)) found:
- 25% of server admins have lost players or friends because of crashes, lag or downtime (53% on shared hosting).
- 51% said ongoing instability could make them stop hosting or playing.

**People already want help.** Crash-handling mods have about 203 million downloads between them: Crash Assistant 94.9M, Neruina 71.6M, Not Enough Crashes (Forge) 23.1M and (Fabric) 13.8M, across [CurseForge](https://www.curseforge.com/minecraft/mc-mods/crash-assistant) and [Modrinth](https://modrinth.com/mod/ix1qq8Ux).

**Most crashes are fixable, but someone has to read the log.**
- The Crash Assistant author says more than 75% of reported problems are common, easily solvable issues ([CurseForge](https://www.curseforge.com/minecraft/mc-mods/crash-assistant)).
- Hosting guides say the cause is usually in the log but buried in a few hundred lines of normal startup output ([GameServerKings](https://www.gameserverkings.com/knowledge-base/minecraft/reading-crash-logs-and-common-errors.md)), and the standard advice is trial and error: remove every mod and add them back in batches ([Apex Hosting](https://apexminecrafthosting.com/guides/minecraft/server-errors/mod-plugin-troubleshooting-guide-minecraft/)).
- Shockbyte asks stuck customers to open a ticket so its technical team can read the crash report ([Shockbyte](https://shockbyte.com/billing/knowledgebase/106/How-to-Find-and-Read-a-Server-Crash-Report.html)). At least five hosts publish their own crash-reading guides.
- All the Mods 10 received 8 crash reports on GitHub in under four weeks, counting open issues only ([ATM10 issues](https://github.com/AllTheMods/ATM-10/issues)).

**A real example.** A Cobblemon server admin deleted mods and made a new world without fixing the crashes. A forum volunteer then read the crash report and named one mod with corrupted saved data; removing it fixed the server, a day after the post ([Minecraft Forum](https://www.minecraftforum.net/forums/support/server-support-and/3225864-cobblemon-server-keeps-crashing-randomly-need-help)). The answer was in the log all along. That is the job this agent does, with the line cited.

**Existing tools only go part of the way.** Crash Assistant and [mclo.gs](https://github.com/aternosorg/mclogs) match known patterns. Our agent investigates the cause, cites the exact log line or known issue for every claim, and says "unclear" when the evidence isn't there.

## How it works

1. **Parser** (`agent/parser.py`) numbers the log and finds the exceptions, the root cause (last `Caused by:`) and the first mod frame in the stack trace.
2. **Knowledge** (`agent/knowledge.py`) pulls known crash issues from **Zetaris** with SQL and matches them to the log.
3. **Investigator** (`agent/investigator.py`) asks **Nemotron through Nightshift** for a JSON diagnosis that cites line numbers and known-issue IDs.
4. **Critic** (`agent/critic.py`) checks every quoted line really is on the cited line. Unsupported claims are rejected with feedback.
5. **Loop** (`agent/loop.py`) retries with the critic's feedback, carrying state forward as a **Markovian** carryover block (`agent/markovian.py`), then drops anything still unsupported. No mod in the stack means "unclear", not a guess.

Every run writes a full trace to `runs/<timestamp>_<name>.json`: the Zetaris query, the carryover sent, raw model replies, critic verdicts and the final answer.

## Sponsor technology

| Sponsor | What we use | Where | How to see it |
|---|---|---|---|
| Zetaris | Known-issues table (25 rows, a Lightning REST table over our JSON) queried with SQL over the Zetaris REST API | `agent/zetaris.py`, `agent/knowledge.py`, `docs/zetaris_setup.sql` | `zetaris` block in each trace; "Fetched 25 known issues" on run |
| Meterless Engine: Markovian | Bounded carryover between attempts in the spec's COMPLETED / REMAINING / DECISIONS / CONTEXT format, cut to an 800-token budget | `agent/markovian.py`, `tests/test_markovian.py` | `markovian`, `carryover_block`, `carryover_sent` in each trace |
| Nightshift (NVIDIA Nemotron) | Primary and only LLM provider: `nvidia/nemotron-3.5-lightning-30b-a3b` via the OpenAI-compatible endpoint | `agent/llm.py`, `check_llm.py` | `raw` replies in each trace; Nightshift Console "Last request" |
| Cursor | Our code editor for the whole build. We used Cursor's AI Agent heavily to write and change code across files until our Agent credits ran out, then kept writing and editing in Cursor by hand. | Every file in `agent/`, `tests/`, `tools/` | Commit history |
Markovian evidence is our own reproducible feature test (`tests/test_markovian.py`). The official conformance suite only loads TypeScript, so we have not run it.

## Results

Eval on the 5 sample logs against the answer key (`python eval.py`, full table in `docs/eval_results.md`):

| Log | What | Expected | Got | Pass |
|---|---|---|---|---|
| log01 | Fabric client, Moonlight Lib null codec | diagnosed | diagnosed, high | yes |
| log02 | Forge watchdog, no mod in stack | unclear | unclear, low | yes |
| log03 | Fabric server, rctmod NullPointerException | diagnosed | diagnosed, high | yes |
| log04 | Quest Giver "Duplicate key Node" | unclear | diagnosed, high | **no** |
| log05 | Watchdog during /locate, BattleTowers | diagnosed | diagnosed, medium | yes |

**4/5 pass.** log04 is an honest miss: the agent blamed the mod that *called* the failing code, while the real cause is a vanilla pathfinding bug. Telling caller from cause is future work (a second critic layer).

**See the critic work without waiting for the model:** `tools/demo_critic.py` feeds the critic one real claim from log05 and two bad ones (a wrong line number and an invented quote). It keeps one and rejects two, with reasons. No LLM call, so it runs instantly.

## Setup (Windows, PowerShell)

You need Python 3.13+ (tested on 3.14) and Git. To run real investigations you also need Nightshift running locally and a Zetaris install with the known-issues table. The tests need neither.

```powershell
git clone https://github.com/JaeJet/2026OctAIHackathon
cd 2026OctAIHackathon
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Then open `.env` and fill in your own Zetaris key and Nightshift Console token. Keys live only in `.env`, which git ignores. (The `Copy-Item` step is needed even just for the tests: `agent/llm.py` checks for the settings when it loads.)

**Run the tests** (works with the placeholder `.env`, no services needed):

```powershell
python -m pytest
```

Expected: 62 passed.

**Critic demo** (no services needed):

```powershell
python tools/demo_critic.py
```

**Check Nightshift is reachable:**

```powershell
python check_llm.py
```

**Investigate one crash log** (what a server admin would do):

```powershell
python -m agent.loop data/sample_logs/log03.txt
```

Runs the full agent once on a single log: parser, Zetaris known issues, Nemotron via Nightshift, the critic, and a retry with Markovian carryover if any claim is rejected. It prints the final diagnosis as JSON and saves the full trace to `runs/<timestamp>_<name>.json` (the path is printed at the end). It doesn't know the right answer; it just reports what the agent concluded. You can point it at any crash log file, not only the samples. One model call takes about 1–3 minutes.

**Score the agent against the answer key** (how we got the Results table):

```powershell
python eval.py              # all sample logs
python eval.py log02 log05  # just some
```

Runs the same agent on each sample log, then compares each answer with the expected one in `data/answer_key.csv` (diagnosed or unclear) and writes a pass/fail table to `docs/eval_results.md`. It also saves a trace for every log in `runs/`. Expect about 1–3 minutes per log, and note that it **overwrites** `docs/eval_results.md`. The model's answers can vary slightly between runs, so the committed file is the run our Results section reports.

In short: `agent.loop` *uses* the agent on one log; `eval.py` *tests* it against known answers.
```

**Zetaris table:** run `docs/zetaris_setup.sql` once in the Zetaris SQL Editor. Zetaris reads `data/known_issues.json` straight from this GitHub repo as a REST table (25 rows).

## Repo layout

```
agent/          parser, knowledge + zetaris, investigator, critic, markovian, loop
data/           sample_logs/, known_issues.csv/.json, answer_key.csv
docs/           eval_results.md, zetaris_setup.sql, output_format.md, demo_traces/
tests/          pytest tests (one file per module)
tools/          csv_to_json.py, clean_forum_log.py, demo_critic.py
eval.py         scores the agent against the answer key
check_llm.py    Nightshift connection check
```

## Limitations

- Caller vs cause (log04): the agent trusts the first mod frame.
- Five evaluated logs; the answer key has rows up to log20 for future runs.
- Speed depends on Nightshift: about 80–160 s per call.

## Team

- **Jaeden Chong - Tech lead:** architecture, agent code, sponsor integration, demo video
- **Albert Kim - Data lead:** sample logs, known-issues table, answer key, slides
- **James Korompis - Docs:** README, setup guide, impact statistics research
