#!/usr/bin/env python3
"""Parse, verify handoff, and archive issue-based submissions.

Preferred issue form fields:

    ### Hole
    fizz-buzz

    ### Language
    python

    ### File extension
    py

    ### Answer code
    ```text
    exact answer bytes as UTF-8 text
    ```

The workflow computes sha256 itself. Notes are allowed in the issue but are not
archived. The parser also accepts the older `answer-base64` fenced format for
exact-byte compatibility.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

FIELD_RE = re.compile(r"^(hole|lang|ext|sha256):\s*(\S+)\s*$", re.MULTILINE)
BASE64_FENCE_RE = re.compile(r"```(?:answer-base64|base64)\s*\n(.*?)\n```", re.DOTALL | re.IGNORECASE)
CODE_FENCE_RE = re.compile(r"```[^\n]*\n(.*?)\n```", re.DOTALL)
HEADING_RE = re.compile(r"^###\s+(.+?)\s*$", re.MULTILINE)
HOLE_RE = re.compile(r"^[a-z0-9-]+$")
LANG_RE = re.compile(r"^[a-z0-9-]+$")
EXT_RE = re.compile(r"^[a-z0-9]+$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_BYTES = 128 * 1024


def run(args: list[str], *, check: bool = True, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if check and proc.returncode:
        raise RuntimeError(f"command failed ({proc.returncode}): {' '.join(args)}\nSTDOUT:\n{proc.stdout[-2000:]}\nSTDERR:\n{proc.stderr[-2000:]}")
    return proc


def out(**items: object) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as f:
        for key, value in items.items():
            f.write(f"{key}={value}\n")


def load_event(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def form_value(body: str, *labels: str) -> str | None:
    wanted = {label.casefold() for label in labels}
    matches = list(HEADING_RE.finditer(body))
    for i, match in enumerate(matches):
        if match.group(1).strip().casefold() not in wanted:
            continue
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        return body[start:end].strip("\n")
    return None


def required_value(fields: dict[str, str], body: str, key: str, *labels: str) -> str:
    value = fields.get(key)
    if value is None:
        value = form_value(body, *labels)
    if value is None or not value.strip():
        raise SystemExit(f"missing required field: {key}")
    return value.strip()


def parse_answer(body: str, provided_sha: str | None) -> tuple[bytes, str]:
    match = BASE64_FENCE_RE.search(body)
    if match:
        encoded = "".join(match.group(1).split())
        try:
            answer = base64.b64decode(encoded, validate=True)
        except Exception as exc:
            raise SystemExit(f"invalid base64: {exc}") from exc
    else:
        section = form_value(body, "Answer code", "Code") or body
        match = CODE_FENCE_RE.search(section)
        if not match:
            raise SystemExit("missing fenced answer code block")
        answer = match.group(1).encode("utf-8")

    if len(answer) >= MAX_BYTES:
        raise SystemExit(f"answer too large: {len(answer)} bytes")
    digest = hashlib.sha256(answer).hexdigest()
    if provided_sha is not None:
        provided_sha = provided_sha.lower()
        if not SHA_RE.fullmatch(provided_sha):
            raise SystemExit("invalid sha256")
        if digest != provided_sha:
            raise SystemExit(f"sha256 mismatch: computed {digest}")
    return answer, digest


def parse_issue(event: dict[str, Any]) -> dict[str, Any]:
    issue = event.get("issue") or {}
    body = issue.get("body") or ""
    fields = dict(FIELD_RE.findall(body))

    hole = required_value(fields, body, "hole", "Hole")
    lang = required_value(fields, body, "lang", "Language")
    ext = required_value(fields, body, "ext", "File extension", "Extension")
    if not HOLE_RE.fullmatch(hole):
        raise SystemExit(f"invalid hole: {hole}")
    if not LANG_RE.fullmatch(lang):
        raise SystemExit(f"invalid lang: {lang}")
    if not EXT_RE.fullmatch(ext):
        raise SystemExit(f"invalid ext: {ext}")

    answer, sha256 = parse_answer(body, fields.get("sha256"))

    return {
        "issue_number": int(issue["number"]),
        "issue_url": issue.get("html_url", ""),
        "author": (issue.get("user") or {}).get("login", ""),
        "hole": hole,
        "lang": lang,
        "ext": ext,
        "sha256": sha256,
        "answer": answer,
        "bytes": len(answer),
        "chars": len(answer.decode("utf-8", "replace")),
        "id": sha256[:16],
    }


def cmd_prepare(event_path: str, output_dir: str) -> int:
    sub = parse_issue(load_event(event_path))
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    answer_path = out_dir / f"answer.{sub['ext']}"
    answer_path.write_bytes(sub["answer"])
    out(
        issue_number=sub["issue_number"],
        issue_url=sub["issue_url"],
        author=sub["author"],
        hole=sub["hole"],
        lang=sub["lang"],
        ext=sub["ext"],
        sha256=sub["sha256"],
        bytes=sub["bytes"],
        chars=sub["chars"],
        id=sub["id"],
        answer_path=str(answer_path),
    )
    print(f"prepared {sub['hole']}/{sub['lang']} {sub['bytes']}B")
    return 0


def load_json(path: Path) -> dict[str, Any] | None:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def existing_index(lang_dir: Path, hole: str, lang: str) -> dict[str, Any]:
    index_path = lang_dir / "index.json"
    if not index_path.exists():
        return {"schema": "codex-golf.index.v1", "hole": hole, "lang": lang, "best": None, "entries": []}
    with open(index_path, encoding="utf-8") as f:
        return json.load(f)


def write_archive_manifest(root: Path = Path("answers")) -> None:
    entries = []
    if root.exists():
        for index_path in sorted(root.glob("*/*/index.json")):
            try:
                index = json.load(open(index_path, encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            entries.append({
                "hole": index.get("hole") or index_path.parents[1].name,
                "lang": index.get("lang") or index_path.parent.name,
                "index": str(index_path).replace("\\", "/"),
                "best": index.get("best"),
                "count": len(index.get("entries", [])),
            })
    root.mkdir(parents=True, exist_ok=True)
    with open(root / "index.js", "w", encoding="utf-8") as f:
        f.write("globalThis.CODEX_GOLF_INDEX = ")
        json.dump({"schema": "codex-golf.archive-index.v1", "entries": entries}, f, indent=2, sort_keys=True)
        f.write(";\n")


def build_archive_commit(sub: dict[str, Any], answer_path: Path) -> dict[str, Any]:
    run(["git", "fetch", "origin", "solutions", "--depth=1"])
    sol_head = run(["git", "rev-parse", "origin/solutions"]).stdout.strip()
    run(["git", "checkout", "-B", "archive-issue-work", "origin/solutions"])

    answer = answer_path.read_bytes()
    digest = hashlib.sha256(answer).hexdigest()
    if digest != sub["sha256"]:
        raise SystemExit("answer file sha256 changed")
    size = len(answer)
    chars = len(answer.decode("utf-8", "replace"))
    hole = sub["hole"]
    lang = sub["lang"]
    ext = sub["ext"]

    lang_dir = Path("answers") / hole / lang
    lang_dir.mkdir(parents=True, exist_ok=True)
    index = existing_index(lang_dir, hole, lang)
    for entry in index.get("entries", []):
        if entry.get("sha256") == digest:
            return {"result": "duplicate", "id": entry["id"], "bytes": size, "hole": hole, "lang": lang}

    id_len = 16
    while True:
        answer_id = digest[:id_len]
        archive_path = lang_dir / f"{answer_id}.{ext}"
        meta_path = lang_dir / f"{answer_id}.meta.json"
        if not archive_path.exists() and not meta_path.exists():
            break
        old_meta = load_json(meta_path)
        if old_meta and old_meta.get("sha256") == digest:
            return {"result": "duplicate", "id": answer_id, "bytes": size, "hole": hole, "lang": lang}
        id_len += 8
        if id_len > 64:
            raise SystemExit("sha256 id collision could not be resolved")

    best_id = index.get("best")
    entries = index.setdefault("entries", [])
    by_id = {entry["id"]: entry for entry in entries}
    previous = by_id.get(best_id) if best_id else None
    previous_bytes = previous.get("bytes") if previous else None
    was_best = previous is None or size < int(previous_bytes)
    merged_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    rel_answer = f"answers/{hole}/{lang}/{answer_id}.{ext}"
    rel_meta = f"answers/{hole}/{lang}/{answer_id}.meta.json"

    archive_path.write_bytes(answer)
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
        "issue": {"number": sub["issue_number"], "url": sub["issue_url"], "author": sub["author"]},
        "verification": {"workflow_run_id": os.environ.get("GITHUB_RUN_ID"), "verifier_ref": "main"},
        "best": {
            "was_best": was_best,
            "previous_best_id": best_id,
            "previous_best_bytes": previous_bytes,
            "previous_best_chars": previous.get("chars") if previous else None,
            "improvement_bytes": (int(previous_bytes) - size) if was_best and previous_bytes is not None else None,
            "improvement_chars": (int(previous.get("chars")) - chars) if was_best and previous and previous.get("chars") is not None else None,
        },
        "source": {"kind": "issue"},
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, sort_keys=True)
        f.write("\n")

    entries.append({
        "id": answer_id,
        "path": rel_answer,
        "meta": rel_meta,
        "bytes": size,
        "chars": chars,
        "sha256": digest,
        "merged_at": merged_at,
        "pr": None,
        "issue": sub["issue_number"],
        "was_best": was_best,
    })
    entries.sort(key=lambda e: (e.get("merged_at") or "", e["id"]))
    if was_best:
        index["best"] = answer_id
        (lang_dir / "best").write_text(answer_id + "\n", encoding="utf-8")
    elif not (lang_dir / "best").exists() and best_id:
        (lang_dir / "best").write_text(best_id + "\n", encoding="utf-8")
    with open(lang_dir / "index.json", "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, sort_keys=True)
        f.write("\n")
    write_archive_manifest()

    run(["git", "config", "user.name", "codex-golf bot"])
    run(["git", "config", "user.email", "actions@github.com"])
    run(["git", "add", str(lang_dir), "answers/index.js"])
    if run(["git", "diff", "--cached", "--quiet"], check=False).returncode == 0:
        raise SystemExit("archive produced no changes")
    tree = run(["git", "write-tree"]).stdout.strip()
    result = "new_best" if was_best else "archived"
    subject = f"{hole}/{lang}: archive {answer_id} ({size}B)"
    body = f"Accepted issue #{sub['issue_number']}. Result: {result}."
    new_commit = run(["git", "commit-tree", tree, "-p", sol_head, "-m", subject, "-m", body]).stdout.strip()
    return {
        "result": "archived",
        "best_result": result,
        "commit": new_commit,
        "id": answer_id,
        "bytes": size,
        "chars": chars,
        "hole": hole,
        "lang": lang,
        "path": rel_answer,
        "previous_best_id": best_id or "none",
        "previous_best_bytes": previous_bytes if previous_bytes is not None else "none",
    }


def cmd_archive(event_path: str, answer_path: str) -> int:
    sub = parse_issue(load_event(event_path))
    answer = Path(answer_path)
    for attempt in range(1, 6):
        result = build_archive_commit(sub, answer)
        if result["result"] == "duplicate":
            out(**result)
            print(f"duplicate: {result['id']}")
            return 0
        push = run(["git", "push", "origin", f"{result['commit']}:solutions"], check=False)
        if push.returncode == 0:
            out(**result)
            print(f"archived {result['id']} ({result['bytes']}B), result={result['best_result']}")
            return 0
        print(f"push race on attempt {attempt}; retrying", file=sys.stderr)
        time.sleep(2 * attempt)
    raise SystemExit("failed to push archive after retries")


def main() -> int:
    if len(sys.argv) < 2:
        raise SystemExit("usage: issue_submission.py prepare <event.json> <out-dir> | archive <event.json> <answer-path>")
    cmd = sys.argv[1]
    if cmd == "prepare" and len(sys.argv) == 4:
        return cmd_prepare(sys.argv[2], sys.argv[3])
    if cmd == "archive" and len(sys.argv) == 4:
        return cmd_archive(sys.argv[2], sys.argv[3])
    raise SystemExit("bad arguments")


if __name__ == "__main__":
    raise SystemExit(main())
