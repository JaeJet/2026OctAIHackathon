# Output format and design decisions

## Input
One modded Minecraft Java Edition crash report (Forge, NeoForge or Fabric), as text.
For now we assume a single file per run.

## Output
```json
{
  "summary": "Server crashed because Mod X needs Mod Y, which isn't installed.",
  "confidence": "high",
  "claims": [
    {
      "text": "Mod X requires Mod Y",
      "evidence": [
        {"type": "log_line", "line": 42, "quote": "requires mod_y, which is missing"},
        {"type": "known_issue", "id": "KI001"}
      ]
    }
  ],
  "fix": "Install Mod Y version 1.2+ or remove Mod X.",
  "status": "diagnosed"
}
```
## Rules
- Every claim needs evidence.
- A quoted log line must really be on that line.
- A known issue ID must come from Zetaris.
- Up to 3 retries. If nothing is proven, status is "unclear".

## Meterless engine: Markovian
**Why:** the investigation takes several steps. Markovian keeps each step small by only passing short notes forward, not the whole history.

**Notes passed between steps:** hypotheses still possible, ones ruled out, what the critic rejected, and evidence (line numbers and issue IDs).

**Where it's used:** `agent/loop.py` (fill in later)

## Not using
Scout Intent, World Model and H-MEM. They're useful for a bigger product, but not needed for this hackathon.

## To check
- Is Markovian a Python library, or does it run through Nightshift?