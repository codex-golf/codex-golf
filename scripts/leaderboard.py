#!/usr/bin/env python3
"""Generate LEADERBOARD.md from answers/<hole>/<lang>/answer.<ext>.

Usage: scripts/leaderboard.py <solutions-checkout> <output-file>

Reads:
- <solutions-checkout>/answers/<hole>/<lang>/answer.<ext>
- <solutions-checkout>/verify/langs.json (lang -> ext mapping; lookup only)

Writes: <output-file> (markdown).
"""
import json
import os
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone


def main():
    if len(sys.argv) != 3:
        print("usage: leaderboard.py <solutions-checkout> <output-file>", file=sys.stderr)
        sys.exit(2)
    root = sys.argv[1]
    out_path = sys.argv[2]

    answers_dir = os.path.join(root, "answers")
    if not os.path.isdir(answers_dir):
        print(f"no answers/ dir at {answers_dir}", file=sys.stderr)
        sys.exit(1)

    # by_hole[hole] -> list of (lang, bytes)
    # by_lang[lang] -> list of (hole, bytes)
    by_hole = defaultdict(list)
    by_lang = defaultdict(list)
    total = 0

    for hole in sorted(os.listdir(answers_dir)):
        hole_dir = os.path.join(answers_dir, hole)
        if not os.path.isdir(hole_dir):
            continue
        for lang in sorted(os.listdir(hole_dir)):
            lang_dir = os.path.join(hole_dir, lang)
            if not os.path.isdir(lang_dir):
                continue
            answers = [f for f in os.listdir(lang_dir) if f.startswith("answer.")]
            if not answers:
                continue
            ans = os.path.join(lang_dir, answers[0])
            try:
                size = os.path.getsize(ans)
            except OSError:
                continue
            by_hole[hole].append((lang, size))
            by_lang[lang].append((hole, size))
            total += 1

    # Recent submissions: git log on answers/
    recent = []
    try:
        log = subprocess.check_output(
            [
                "git", "-C", root, "log",
                "--pretty=format:%h\t%aI\t%s",
                "--name-only",
                "-n", "60",
                "--",
                "answers",
            ],
            text=True,
        )
        cur = None
        for line in log.splitlines():
            if not line:
                if cur and cur.get("file"):
                    recent.append(cur)
                cur = None
                continue
            if cur is None:
                parts = line.split("\t", 2)
                if len(parts) == 3:
                    cur = {"sha": parts[0], "date": parts[1], "msg": parts[2], "file": None}
            else:
                if line.startswith("answers/") and cur and cur.get("file") is None:
                    cur["file"] = line
        if cur and cur.get("file"):
            recent.append(cur)
    except subprocess.CalledProcessError:
        pass
    recent = recent[:30]

    # Render markdown
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# codex.golf leaderboard",
        "",
        f"**Auto-generated** \u2014 {now}",
        "",
        f"Total entries: **{total}** \u00b7 holes: **{len(by_hole)}** \u00b7 langs: **{len(by_lang)}**",
        "",
        "## By hole",
        "",
    ]
    for hole in sorted(by_hole):
        entries = sorted(by_hole[hole], key=lambda e: (e[1], e[0]))
        lines.append(f"### `{hole}`")
        lines.append("")
        lines.append("| lang | bytes |")
        lines.append("|------|------:|")
        for lang, size in entries:
            lines.append(f"| `{lang}` | {size} |")
        lines.append("")

    lines += ["## By lang", ""]
    for lang in sorted(by_lang):
        entries = sorted(by_lang[lang], key=lambda e: (e[1], e[0]))
        lines.append(f"### `{lang}`")
        lines.append("")
        lines.append("| hole | bytes |")
        lines.append("|------|------:|")
        for hole, size in entries:
            lines.append(f"| `{hole}` | {size} |")
        lines.append("")

    if recent:
        lines += ["## Recent submissions", "", "| commit | date | submission |", "|--------|------|------------|"]
        for r in recent:
            short_date = r["date"][:10]
            lines.append(f"| `{r['sha']}` | {short_date} | {r['msg']} |")
        lines.append("")

    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"wrote {out_path} ({total} entries)", file=sys.stderr)


if __name__ == "__main__":
    main()
