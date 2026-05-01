#!/usr/bin/env python3
"""Generate LEADERBOARD.md from archive indexes.

Usage: scripts/leaderboard.py <solutions-checkout> <output-file>

Reads:
- <solutions-checkout>/answers/<hole>/<lang>/index.json
- <solutions-checkout>/answers/<hole>/<lang>/best

Writes: <output-file> (markdown).
"""
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def entry_label(entry):
    pr = entry.get("pr")
    if pr:
        return f"PR #{pr} / `{entry['id']}`"
    return f"`{entry['id']}`"


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

    by_hole = defaultdict(list)
    by_lang = defaultdict(list)
    recent = []
    total_archived = 0

    for hole in sorted(os.listdir(answers_dir)):
        hole_dir = os.path.join(answers_dir, hole)
        if not os.path.isdir(hole_dir):
            continue
        for lang in sorted(os.listdir(hole_dir)):
            lang_dir = os.path.join(hole_dir, lang)
            index_path = os.path.join(lang_dir, "index.json")
            best_path = os.path.join(lang_dir, "best")
            if not os.path.isfile(index_path) or not os.path.isfile(best_path):
                continue
            index = load_json(index_path)
            entries = index.get("entries", [])
            total_archived += len(entries)
            by_id = {entry["id"]: entry for entry in entries}
            with open(best_path, encoding="utf-8") as f:
                best_id = f.read().strip()
            best = by_id.get(best_id)
            if not best:
                continue
            by_hole[hole].append((lang, best["bytes"], best_id))
            by_lang[lang].append((hole, best["bytes"], best_id))
            recent.extend(entries)

    recent.sort(key=lambda e: (e.get("merged_at") or "", e.get("id") or ""), reverse=True)
    recent = recent[:30]

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    best_total = sum(len(v) for v in by_hole.values())
    lines = [
        "# codex.golf leaderboard",
        "",
        f"**Auto-generated** — {now}",
        "",
        f"Best entries: **{best_total}** · archived entries: **{total_archived}** · holes: **{len(by_hole)}** · langs: **{len(by_lang)}**",
        "",
        "## Best by hole",
        "",
    ]

    for hole in sorted(by_hole):
        entries = sorted(by_hole[hole], key=lambda e: (e[1], e[0]))
        lines += [f"### `{hole}`", "", "| lang | bytes | entry |", "|------|------:|-------|"]
        for lang, size, answer_id in entries:
            lines.append(f"| `{lang}` | {size} | `{answer_id}` |")
        lines.append("")

    lines += ["## Best by lang", ""]
    for lang in sorted(by_lang):
        entries = sorted(by_lang[lang], key=lambda e: (e[1], e[0]))
        lines += [f"### `{lang}`", "", "| hole | bytes | entry |", "|------|------:|-------|"]
        for hole, size, answer_id in entries:
            lines.append(f"| `{hole}` | {size} | `{answer_id}` |")
        lines.append("")

    if recent:
        lines += ["## Recent accepted entries", "", "| merged | hole | lang | bytes | result | entry |", "|--------|------|------|------:|--------|-------|"]
        for entry in recent:
            merged = (entry.get("merged_at") or "")[:10]
            result = "best" if entry.get("was_best") else "archive"
            lines.append(
                f"| {merged} | `{entry.get('path','').split('/')[1] if entry.get('path') else '?'}` | "
                f"`{entry.get('path','').split('/')[2] if entry.get('path') else '?'}` | "
                f"{entry.get('bytes')} | {result} | {entry_label(entry)} |"
            )
        lines.append("")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"wrote {out_path} ({best_total} best, {total_archived} archived)", file=sys.stderr)


if __name__ == "__main__":
    main()
