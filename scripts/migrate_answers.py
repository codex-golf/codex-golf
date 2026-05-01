#!/usr/bin/env python3
"""Migrate legacy answers/<hole>/<lang>/answer.<ext> files to archive layout."""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def main():
    if len(sys.argv) != 2:
        print("usage: migrate_answers.py <solutions-checkout>", file=sys.stderr)
        sys.exit(2)
    root = Path(sys.argv[1])
    answers = root / "answers"
    if not answers.is_dir():
        print(f"no answers dir: {answers}", file=sys.stderr)
        sys.exit(1)

    migrated = 0
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    for answer_path in sorted(answers.glob("*/*/answer.*")):
        hole = answer_path.parents[1].name
        lang = answer_path.parent.name
        ext = answer_path.name.split(".", 1)[1]
        data = answer_path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        answer_id = digest[:16]
        archive_path = answer_path.parent / f"{answer_id}.{ext}"
        meta_path = answer_path.parent / f"{answer_id}.meta.json"
        if archive_path.exists() or meta_path.exists():
            raise SystemExit(f"archive target already exists for {answer_path}: {answer_id}")

        size = len(data)
        chars = len(data.decode("utf-8", "replace"))
        rel_answer = archive_path.relative_to(root).as_posix()
        rel_meta = meta_path.relative_to(root).as_posix()
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
            "merged_at": now,
            "pr": None,
            "verification": None,
            "best": {
                "was_best": True,
                "previous_best_id": None,
                "previous_best_bytes": None,
                "previous_best_chars": None,
                "improvement_bytes": None,
                "improvement_chars": None,
            },
            "source": {"kind": "legacy-single-answer-migration"},
        }
        entry = {
            "id": answer_id,
            "path": rel_answer,
            "meta": rel_meta,
            "bytes": size,
            "chars": chars,
            "sha256": digest,
            "merged_at": now,
            "pr": None,
            "was_best": True,
        }
        index = {
            "schema": "codex-golf.index.v1",
            "hole": hole,
            "lang": lang,
            "best": answer_id,
            "entries": [entry],
        }

        archive_path.write_bytes(data)
        meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (answer_path.parent / "best").write_text(answer_id + "\n", encoding="utf-8")
        (answer_path.parent / "index.json").write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        answer_path.unlink()
        migrated += 1
        print(f"migrated {hole}/{lang}: {answer_id} ({size}B)")

    print(f"migrated {migrated} answer(s)")


if __name__ == "__main__":
    main()
