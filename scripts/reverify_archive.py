#!/usr/bin/env python3
"""Reverify every archived answer entry."""
import json
import os
import subprocess
import sys
from pathlib import Path


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_output(**items):
    out = os.environ.get("GITHUB_OUTPUT")
    if not out:
        return
    with open(out, "a", encoding="utf-8") as f:
        for key, value in items.items():
            f.write(f"{key}={value}\n")


def main():
    if len(sys.argv) != 5:
        print("usage: reverify_archive.py <solutions> <main> <upstream> <regressions.md>", file=sys.stderr)
        sys.exit(2)
    solutions = Path(sys.argv[1])
    main_root = Path(sys.argv[2])
    upstream = Path(sys.argv[3])
    regressions = Path(sys.argv[4])
    answers = solutions / "answers"
    pass_count = 0
    fail_count = 0
    details = []

    for index_path in sorted(answers.glob("*/*/index.json")):
        hole = index_path.parents[1].name
        lang = index_path.parent.name
        try:
            index = load_json(index_path)
        except Exception as exc:
            fail_count += 1
            details.append(f"### `{hole} / {lang}`\n\nBad index: `{index_path}`: {exc}\n")
            continue

        entries = index.get("entries", [])
        by_id = {entry.get("id"): entry for entry in entries}
        best = index.get("best")
        if best not in by_id:
            fail_count += 1
            details.append(f"### `{hole} / {lang}`\n\nInvalid best pointer: `{best}`\n")

        best_entry = min(entries, key=lambda e: (int(e.get("bytes", 10**18)), e.get("id", ""))) if entries else None
        if best_entry and best_entry.get("id") != best:
            fail_count += 1
            details.append(f"### `{hole} / {lang}`\n\nBest pointer `{best}` is not shortest; shortest is `{best_entry.get('id')}`.\n")

        for entry in entries:
            rel = entry.get("path")
            answer = solutions / rel if rel else None
            if not answer or not answer.is_file():
                fail_count += 1
                details.append(f"### `{hole} / {lang}`\n\nMissing answer file for entry `{entry.get('id')}`: `{rel}`\n")
                continue
            data = answer.read_bytes()
            if len(data) != int(entry.get("bytes", -1)):
                fail_count += 1
                details.append(f"### `{hole} / {lang}`\n\nByte count mismatch for `{rel}`.\n")
                continue
            cmd = [str(main_root / "verify" / "run.sh"), hole, lang, str(answer), str(upstream)]
            proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if proc.returncode == 0:
                pass_count += 1
                print(f"[PASS] {hole}/{lang}/{entry.get('id')}")
            else:
                fail_count += 1
                print(f"[FAIL] {hole}/{lang}/{entry.get('id')}")
                out = "\n".join(proc.stdout.splitlines()[:40])
                details.append(f"### `{hole} / {lang}`\n\nFile: `{rel}`\n\n```\n{out}\n```\n")

    regressions.write_text("\n".join(details), encoding="utf-8")
    print(f"PASS={pass_count}, FAIL={fail_count}")
    write_output(**{"pass": pass_count, "fail": fail_count})


if __name__ == "__main__":
    main()
