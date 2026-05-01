#!/usr/bin/env python3
"""End-to-end GitHub Actions harness for fork-origin PRs.

This intentionally uses a real fork, not throwaway branches in the base repo,
so it exercises the same security boundary as outside contributors:

  fork -> push branch to fork -> PR into base:solutions -> Verify PR ->
  Merge on Verify -> assert final PR state/labels.

Default case is a known-failing 05AB1E fizz-buzz answer so it is safe to run
without changing `solutions`. Use --case pass-* only when you intentionally want
an auto-merge test that may add an answer to solutions.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

BASE_REPO = "codex-golf/codex-golf"
DEFAULT_FORK_NAME = "codex-golf-e2e"
DEFAULT_CORPUS = os.environ.get("CODEX_GOLF_CORPUS")

FORBIDDEN_PATTERNS = [
    pat for pat in os.environ.get("CODEX_GOLF_FORBIDDEN_RE", "").splitlines()
    if pat.strip()
]
BLOCKED_FORK_OWNERS = {
    owner.strip().lower()
    for owner in os.environ.get("CODEX_GOLF_BLOCKED_FORK_OWNERS", "").replace(",", "\n").splitlines()
    if owner.strip()
}

CASES: dict[str, dict[str, Any]] = {
    # Safe default: official runner rejects this answer because multiples of 15
    # output Fizz instead of FizzBuzz.
    "fail-05ab1e": {
        "hole": "fizz-buzz",
        "lang": "05ab1e",
        "source_ext": "05ab1e",
        "dest_ext": "5ab1e",
        "expect": "fail",
        "title_prefix": "e2e-fail",
    },
    # Pass cases are intentionally explicit opt-in because they are expected to
    # auto-merge and therefore mutate solutions.
    "pass-basic": {
        "hole": "fizz-buzz",
        "lang": "basic",
        "source_ext": "bas",
        "dest_ext": "bas",
        "expect": "pass",
        "title_prefix": "e2e-pass",
    },
    "pass-python-divisors": {
        "hole": "divisors",
        "lang": "python",
        "source_ext": "py",
        "dest_ext": "py",
        "expect": "pass",
        "title_prefix": "e2e-pass",
    },
    "pass-python-leap-years": {
        "hole": "leap-years",
        "lang": "python",
        "source_ext": "py",
        "dest_ext": "py",
        "expect": "pass",
        "title_prefix": "e2e-pass",
    },
}


def run(cmd: list[str], *, cwd: Path | None = None, check: bool = True, capture: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        check=False,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )
    if check and proc.returncode:
        out = (proc.stdout or "")[-2000:]
        err = (proc.stderr or "")[-2000:]
        raise RuntimeError(f"command failed ({proc.returncode}): {' '.join(cmd)}\nSTDOUT:\n{out}\nSTDERR:\n{err}")
    return proc


def gh_json(args: list[str]) -> Any:
    return json.loads(run(["gh", *args]).stdout)


def safe_text(*texts: str) -> None:
    blob = "\n".join(texts)
    for pat in FORBIDDEN_PATTERNS:
        if re.search(pat, blob, re.I):
            raise RuntimeError(f"refusing PR-visible text matching forbidden pattern: {pat}")


def repo_exists(repo: str) -> bool:
    return run(["gh", "repo", "view", repo, "--json", "nameWithOwner"], check=False).returncode == 0


def ensure_fork(base: str, fork_owner: str, fork_name: str) -> str:
    fork = f"{fork_owner}/{fork_name}"
    if repo_exists(fork):
        info = gh_json(["repo", "view", fork, "--json", "nameWithOwner,isFork,parent"])
        parent = (info.get("parent") or {}).get("nameWithOwner")
        if not info.get("isFork"):
            raise RuntimeError(f"{fork} exists but is not a fork (parent={parent!r})")
        # Some GitHub API responses omit parent for forks after repository
        # recreation, even though cross-repo PRs still work. Reject explicit
        # mismatches, but accept a missing parent and let PR creation verify the
        # relationship.
        if parent and parent != base:
            raise RuntimeError(f"{fork} exists but is not a fork of {base} (parent={parent!r})")
        return fork

    print(f"Creating fork {fork} from {base} ...")
    # GitHub supports `name` for forks; using a non-default name avoids clashing
    # with pre-existing personal repos named codex-golf.
    run(["gh", "api", "-X", "POST", f"repos/{base}/forks", "-f", f"name={fork_name}"])

    for _ in range(60):
        if repo_exists(fork):
            return fork
        time.sleep(2)
    raise RuntimeError(f"fork did not appear: {fork}")


def source_file(corpus: Path, hole: str, lang: str, source_ext: str) -> Path:
    src = corpus / hole / f"{lang}.{source_ext}"
    if not src.exists():
        raise RuntimeError(f"missing corpus source: {src}")
    return src


def make_branch_name(case: str) -> str:
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    safe = re.sub(r"[^a-zA-Z0-9-]", "-", case).lower()
    return f"e2e-{safe}-{stamp}"


def latest_verify_run(repo: str, title: str) -> dict[str, Any] | None:
    # Do not pass --workflow here: this pull_request workflow lives on the
    # non-default solutions branch, and GitHub's name filter can fail to resolve
    # it even while runs exist. Filter the recent runs client-side instead.
    runs = gh_json([
        "run", "list", "--repo", repo, "--limit", "50",
        "--json", "databaseId,workflowName,displayTitle,status,conclusion,url",
    ])
    for run_info in runs:
        if run_info.get("workflowName") == "Verify PR" and run_info.get("displayTitle") == title:
            return run_info
    return None


def wait_pr(repo: str, number: int, title: str, expect: str, timeout: int) -> dict[str, Any]:
    deadline = time.time() + timeout
    last: dict[str, Any] = {}
    while time.time() < deadline:
        run_info = latest_verify_run(repo, title)
        if run_info and run_info.get("conclusion") == "action_required":
            return {"blocked": "action_required", "verify_run": run_info}

        pr = gh_json([
            "pr", "view", str(number), "--repo", repo,
            "--json", "state,labels,mergeCommit,url,comments",
        ])
        labels = {label["name"] for label in pr.get("labels", [])}
        state = pr.get("state")
        last = pr
        if expect == "pass" and state == "MERGED" and "verify-pass" in labels:
            pr["verify_run"] = run_info
            return pr
        if expect == "fail" and state == "OPEN" and "verify-fail" in labels:
            pr["verify_run"] = run_info
            return pr
        time.sleep(15)
    raise TimeoutError(f"PR #{number} did not reach expected {expect!r} state before timeout; last={last}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a real fork-origin PR E2E test.")
    parser.add_argument("--base", default=BASE_REPO)
    parser.add_argument("--fork-owner", required=True, help="Owner of the test fork")
    parser.add_argument("--fork-name", default=DEFAULT_FORK_NAME)
    parser.add_argument("--case", choices=sorted(CASES), default="fail-05ab1e")
    parser.add_argument("--corpus", type=Path, default=Path(DEFAULT_CORPUS) if DEFAULT_CORPUS else None,
                        help="Path to local test corpus, or set CODEX_GOLF_CORPUS")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--keep-pr", action="store_true", help="Do not close failing test PRs after assertion")
    parser.add_argument("--allow-merge", action="store_true", help="Required for pass cases because they mutate solutions")
    args = parser.parse_args()

    if args.corpus is None:
        raise RuntimeError("missing --corpus (or CODEX_GOLF_CORPUS)")
    case = CASES[args.case]
    if case["expect"] == "pass" and not args.allow_merge:
        raise RuntimeError("pass cases auto-merge into solutions; rerun with --allow-merge if intentional")

    fork_owner = args.fork_owner
    if fork_owner.lower() in BLOCKED_FORK_OWNERS:
        raise RuntimeError(f"refusing blocked fork owner: {fork_owner}")
    fork = ensure_fork(args.base, fork_owner, args.fork_name)

    hole = case["hole"]
    lang = case["lang"]
    dest_ext = case.get("dest_ext", case["source_ext"])
    src = source_file(args.corpus, hole, lang, case["source_ext"])
    size = src.stat().st_size
    branch = make_branch_name(args.case)
    title = f"{case['title_prefix']}/{hole}/{lang}: {size}B"
    body = f"Test fork-origin PR flow for {hole}/{lang} ({size}B)."
    commit = f"{case['title_prefix']}/{hole}/{lang}: {size}B"
    safe_text(title, body, commit)

    tmp = Path(tempfile.mkdtemp(prefix="codex-golf-e2e-"))
    try:
        print(f"Cloning fork {fork} into {tmp} ...")
        run(["git", "clone", f"https://github.com/{fork}.git", "work"], cwd=tmp, capture=False)
        work = tmp / "work"
        run(["git", "remote", "add", "base", f"https://github.com/{args.base}.git"], cwd=work)
        run(["git", "fetch", "base", "solutions", "--depth=1"], cwd=work, capture=False)
        run(["git", "checkout", "-B", branch, "FETCH_HEAD"], cwd=work)

        dest = work / "answers" / hole / lang / f"answer.{dest_ext}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        run(["git", "add", str(dest.relative_to(work))], cwd=work)
        run(["git", "commit", "-m", commit], cwd=work)
        run(["git", "push", "--force", "origin", f"HEAD:{branch}"], cwd=work, capture=False)

        print(f"Opening PR from {fork}:{branch} -> {args.base}:solutions ...")
        url = run([
            "gh", "pr", "create", "--repo", args.base,
            "--head", f"{fork_owner}:{branch}", "--base", "solutions",
            "--title", title, "--body", body,
        ]).stdout.strip()
        number = int(url.rstrip("/").split("/")[-1])
        print(f"PR #{number}: {url}")

        # `gh pr checks --watch` gives human-readable progress. It exits nonzero
        # for expected-fail cases, so do not use it as the assertion source.
        run(["gh", "pr", "checks", str(number), "--repo", args.base, "--watch"], check=False, capture=False)

        pr = wait_pr(args.base, number, title, case["expect"], args.timeout)
        if pr.get("blocked") == "action_required":
            print(json.dumps({
                "pr": number,
                "url": url,
                "state": "BLOCKED",
                "reason": "GitHub requires repository admin approval before running fork PR workflows",
                "verify_run": pr.get("verify_run"),
            }, indent=2))
            if not args.keep_pr:
                run(["gh", "pr", "close", str(number), "--repo", args.base, "--comment", "Closing fork-origin E2E probe: workflow is blocked at action_required and requires repository admin approval."])
                print(f"Closed action_required PR #{number}")
            run(["git", "push", "origin", f":{branch}"], cwd=work, check=False, capture=False)
            return 2

        labels = [label["name"] for label in pr.get("labels", [])]
        print(json.dumps({
            "pr": number,
            "url": url,
            "state": pr["state"],
            "labels": labels,
            "expect": case["expect"],
            "verify_run": pr.get("verify_run"),
        }, indent=2))

        if case["expect"] == "fail" and not args.keep_pr:
            run(["gh", "pr", "close", str(number), "--repo", args.base, "--comment", "Closing completed fork-origin E2E failure test PR."])
            print(f"Closed expected-fail PR #{number}")

        run(["git", "push", "origin", f":{branch}"], cwd=work, check=False, capture=False)
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
