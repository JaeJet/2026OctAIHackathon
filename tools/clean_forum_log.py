import re
import sys
from pathlib import Path

# Lines that are forum list formatting, not part of the real log (log02 style)
JUNK = {"[*]", "[/s]", "[/numlist]", "List tags are malformed.", ""}


def remove_forum_junk(text: str) -> str:
    out = []
    for line in text.splitlines():
        if line.strip() in JUNK:
            continue
        out.append(line.replace("Chunks[s]", "Chunks[S]"))
    return "\n".join(out) + "\n"


def reflow(text: str) -> str:
    HEADER = "---- Minecraft Crash Report ----"

    # 1. Join everything (also fixes words the forum split, like "Trans" / "fer")
    text = text.replace("\r", "").replace("\n", "")
    text = text.replace(HEADER + HEADER, HEADER)

    # 2. Take the header out so the section-header rule can't split it
    has_header = HEADER in text
    text = text.replace(HEADER, "", 1)

    # 3. Section headers like "-- Head --" get their own line
    text = re.sub(r"(-- [A-Z][\w ]* --)", r"\n\1\n", text)

    # 4. Break before each of these markers
    markers = [
        r" ?(?=\bat (?:[A-Za-z][\w-]*/|[a-z][\w$]*\.))",   # stack frames
        r"(?<!Caused by: )(?=(?:java|javax|net|com|org)\.[\w.$]*(?:Exception|Error)(?::|\s|$))",  # main exception
        r" ?(?=Caused by: )",
        r" ?(?=\.\.\. \d+ more)",
        r"(?=// )", r"(?=Time:)", r"(?=Description:)",
        r"(?=Details:)", r"(?=Thread:)", r"(?=Stacktrace:)",
        r"(?=A detailed walkthrough)", r"(?<!-)(?=-{20,})",
    ]
    for m in markers:
        text = re.sub(m, "\n", text)

    lines = [line.strip() for line in text.split("\n")]
    body = "\n".join(line for line in lines if line) + "\n"
    return (HEADER + "\n" + body) if has_header else body


def main():
    if len(sys.argv) < 3:
        print("Usage: python tools/clean_forum_log.py INPUT OUTPUT [--reflow]")
        sys.exit(1)

    src = Path(sys.argv[1])
    dst = Path(sys.argv[2])
    text = src.read_text(encoding="utf-8-sig", errors="replace")
    lines_in = len(text.splitlines())

    if "--reflow" in sys.argv:
        text = reflow(text)
    else:
        text = remove_forum_junk(text)

    dst.write_text(text, encoding="utf-8")
    print(f"{lines_in} lines in, {len(text.splitlines())} lines out -> {dst}")


if __name__ == "__main__":
    main()