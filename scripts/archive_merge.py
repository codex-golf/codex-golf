#!/usr/bin/env python3
"""Archive a verified PR answer into the solutions branch layout.

Run from a checkout of the current `solutions` branch. The script fetches the PR
head, re-reads the staging answer from that commit, recomputes all facts, writes
content-addressed archive files, creates a transformed merge commit, and pushes
it to `origin/solutions`.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PATH_RE = re.compile(r"^answers/([a-z0-9-]+)/([a-z0-9-]+)/answer\.([a-z0-9]+)$")


def run(args, *, text=True, input=None):
    return subprocess.run(args, text=text, input=input, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout


def write_output(**items):
    out = os.environ.get("GITHUB_OUTPUT")
    if not out:
        return
    with open(out, "a", encoding="utf-8") as f:
        for key, value in items.items():
            f.write(f"{key}={value}\n")


def load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def git_show_bytes(ref, path):
    return subprocess.run(["git", "show", f"{ref}:{path}"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout


def existing_index(lang_dir):
    index_path = lang_dir / "index.json"
    if not index_path.exists():
        return {
            "schema": "codex-golf.index.v1",
            "hole": lang_dir.parent.name,
            "lang": lang_dir.name,
            "best": None,
            "entries": [],
        }
    with open(index_path, encoding="utf-8") as f:
        return json.load(f)


def main():
    if len(sys.argv) != 2:
        print("usage: archive_merge.py <verdict.json>", file=sys.stderr)
        sys.exit(2)

    verdict = load_json(sys.argv[1])
    if not verdict:
        print("::error::missing verdict", file=sys.stderr)
        sys.exit(1)
    if verdict.get("schema") != "codex-golf.verdict.v2":
        print(f"::error::bad verdict schema: {verdict.get('schema')}", file=sys.stderr)
        sys.exit(1)
    if verdict.get("status") != "pass":
        print("::error::archive_merge.py only handles pass verdicts", file=sys.stderr)
        sys.exit(1)

    pr = int(verdict["pr_number"])
    head_sha = verdict["head_sha"]
    file_path = verdict["file"]
    match = PATH_RE.match(file_path)
    if not match:
        print(f"::error::bad answer path: {file_path}", file=sys.stderr)
        sys.exit(1)
    hole, lang, ext = match.groups()

    run(["git", "fetch", "origin", "solutions", "--depth=1"])
    sol_head = run(["git", "rev-parse", "origin/solutions"]).strip()
    run(["git", "checkout", "-B", "archive-work", "origin/solutions"])

    run(["git", "fetch", "origin", f"pull/{pr}/head", "--depth=1"])
    pr_head = run(["git", "rev-parse", "FETCH_HEAD"]).strip()
    if pr_head != head_sha:
        print(f"::error::PR head changed: fetched={pr_head} verdict={head_sha}", file=sys.stderr)
        sys.exit(1)

    answer = git_show_bytes(pr_head, file_path)
    digest = hashlib.sha256(answer).hexdigest()
    size = len(answer)
    chars = len(answer.decode("utf-8", "replace"))
    if digest != verdict.get("sha256"):
        print("::error::sha256 mismatch between verdict and PR head", file=sys.stderr)
        sys.exit(1)
    if size != int(verdict.get("bytes", -1)):
        print("::error::byte count mismatch between verdict and PR head", file=sys.stderr)
        sys.exit(1)

    lang_dir = Path("answers") / hole / lang
    lang_dir.mkdir(parents=True, exist_ok=True)
    index = existing_index(lang_dir)

    for entry in index.get("entries", []):
        if entry.get("sha256") == digest:
            existing = entry["id"]
            print(f"duplicate: {existing}")
            write_output(result="duplicate", id=existing, bytes=size, hole=hole, lang=lang)
            return

    id_len = 16
    while True:
        answer_id = digest[:id_len]
        archive_path = lang_dir / f"{answer_id}.{ext}"
        meta_path = lang_dir / f"{answer_id}.meta.json"
        if not archive_path.exists() and not meta_path.exists():
            break
        old_meta = load_json(meta_path)
        if old_meta and old_meta.get("sha256") == digest:
            write_output(result="duplicate", id=answer_id, bytes=size, hole=hole, lang=lang)
            return
        id_len += 8
        if id_len > 64:
            print("::error::sha256 id collision could not be resolved", file=sys.stderr)
            sys.exit(1)

    best_id = index.get("best")
    entries = index.setdefault("entries", [])
    by_id = {entry["id"]: entry for entry in entries}
    previous = by_id.get(best_id) if best_id else None
    previous_bytes = previous.get("bytes") if previous else None
    was_best = previous is None or size < int(previous_bytes)

    merged_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    rel_answer = f"answers/{hole}/{lang}/{answer_id}.{ext}"
    rel_meta = f"answers/{hole}/{lang}/{answer_id}.meta.json"
    pr_url = f"https://github.com/{os.environ.get('REPO', '')}/pull/{pr}"

    meta = {
        "schema": "codex-golf.answer.v1",
        "id": answer_id,
        "sha256": digest,
        "hole": hole,
        "lang": lang,
        "ext": ext,
        "path": rel_answer,
        "bytes": size,
        "chars": chars,
        "submitted_at": None,
        "merged_at": merged_at,
        "pr": {
            "number": pr,
            "url": pr_url,
            "author": verdict.get("author"),
            "head_repo": verdict.get("head_repo"),
            "head_sha": head_sha,
            "base_sha": verdict.get("base_sha"),
        },
        "verification": {
            "workflow_run_id": os.environ.get("VERIFY_RUN_ID"),
            "workflow_run_url": verdict.get("run_url"),
            "verifier_ref": "main",
            "upstream_ref": "master",
        },
        "best": {
            "was_best": was_best,
            "previous_best_id": best_id,
            "previous_best_bytes": previous_bytes,
            "previous_best_chars": previous.get("chars") if previous else None,
            "improvement_bytes": (int(previous_bytes) - size) if was_best and previous_bytes is not None else None,
            "improvement_chars": (int(previous.get("chars")) - chars) if was_best and previous and previous.get("chars") is not None else None,
        },
        "source": {"kind": "pull_request"},
    }

    archive_path.write_bytes(answer)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, sort_keys=True)
        f.write("\n")

    entry = {
        "id": answer_id,
        "path": rel_answer,
        "meta": rel_meta,
        "bytes": size,
        "chars": chars,
        "sha256": digest,
        "merged_at": merged_at,
        "pr": pr,
        "was_best": was_best,
    }
    entries.append(entry)
    entries.sort(key=lambda e: (e.get("merged_at") or "", e["id"]))
    if was_best:
        index["best"] = answer_id
        (lang_dir / "best").write_text(answer_id + "\n", encoding="utf-8")
    elif not (lang_dir / "best").exists() and best_id:
        (lang_dir / "best").write_text(best_id + "\n", encoding="utf-8")
    index["entries"] = entries
    with open(lang_dir / "index.json", "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, sort_keys=True)
        f.write("\n")

    run(["git", "config", "user.name", "codex-golf bot"])
    run(["git", "config", "user.email", "actions@github.com"])
    run(["git", "add", str(lang_dir)])
    staged = subprocess.run(["git", "diff", "--cached", "--quiet"])
    if staged.returncode == 0:
        print("::error::archive produced no changes", file=sys.stderr)
        sys.exit(1)

    tree = run(["git", "write-tree"]).strip()
    result = "new_best" if was_best else "archived"
    subject = f"{hole}/{lang}: archive {answer_id} ({size}B)"
    body = f"Accepted PR #{pr}. Result: {result}."
    new_commit = run([
        "git", "commit-tree", tree,
        "-p", sol_head,
        "-p", pr_head,
        "-m", subject,
        "-m", body,
    ]).strip()
    run(["git", "push", "origin", f"{new_commit}:solutions"])

    print(f"archived {answer_id} ({size}B), result={result}")
    write_output(
        result="archived",
        best_result=result,
        id=answer_id,
        bytes=size,
        chars=chars,
        hole=hole,
        lang=lang,
        path=rel_answer,
        previous_best_id=best_id or "none",
        previous_best_bytes=previous_bytes if previous_bytes is not None else "none",
    )


if __name__ == "__main__":
    main()
