#!/usr/bin/env python3
"""Sync the upstream mirror and rebuild VERIFY_LOCK.

The lock intentionally stays compact:

    upstream_ref <40-hex-sha>
    lang_image <lang> sha256:<digest>

Only languages already present in the solutions archive are locked. New
languages add one line when they are first accepted/needed.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_URL = "https://github.com/code-golf/code-golf.git"
LOCK_PATH = ROOT / "verify" / "VERIFY_LOCK"
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
LANG_RE = re.compile(r"^[a-z0-9-]+$")
ACCEPT = ", ".join(
    [
        "application/vnd.docker.distribution.manifest.v2+json",
        "application/vnd.docker.distribution.manifest.list.v2+json",
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.oci.image.index.v1+json",
    ]
)


def run(*cmd: str, capture: bool = False, check: bool = True) -> str:
    kwargs = {"cwd": ROOT, "text": True, "check": check}
    if capture:
        kwargs["stdout"] = subprocess.PIPE
    result = subprocess.run(cmd, **kwargs)
    return result.stdout.strip() if capture else ""


def ensure_remote() -> None:
    remotes = run("git", "remote", capture=True).splitlines()
    if "upstream" not in remotes:
        run("git", "remote", "add", "upstream", UPSTREAM_URL)
    else:
        run("git", "remote", "set-url", "upstream", UPSTREAM_URL)


def resolve_upstream_ref(ref: str | None) -> str:
    ensure_remote()
    if ref:
        run("git", "fetch", "--no-tags", "upstream", ref)
    else:
        run("git", "fetch", "--no-tags", "upstream", "master")
    sha = run("git", "rev-parse", "FETCH_HEAD", capture=True)
    if not SHA_RE.fullmatch(sha):
        raise SystemExit(f"invalid upstream sha: {sha}")
    return sha


def archived_languages() -> list[str]:
    run("git", "fetch", "--no-tags", "origin", "solutions")
    files = run("git", "ls-tree", "-r", "--name-only", "origin/solutions", "--", "answers", capture=True)
    langs: set[str] = set()
    for path in files.splitlines():
        parts = path.split("/")
        if len(parts) >= 4 and parts[0] == "answers":
            lang = parts[2]
            if LANG_RE.fullmatch(lang):
                langs.add(lang)
    if not langs:
        raise SystemExit("no archived languages found in origin/solutions")
    return sorted(langs)


def validate_languages_in_upstream(upstream_sha: str, langs: list[str]) -> None:
    dockerfile = run("git", "show", f"{upstream_sha}:docker/live.Dockerfile", capture=True)
    missing = []
    for lang in langs:
        pattern = re.compile(rf"^\s*COPY --from=codegolf/lang-{re.escape(lang)}\s", re.MULTILINE)
        if not pattern.search(dockerfile):
            missing.append(lang)
    if missing:
        raise SystemExit("language(s) missing from pinned upstream docker/live.Dockerfile: " + ", ".join(missing))


def docker_token(repo: str) -> str:
    url = f"https://auth.docker.io/token?service=registry.docker.io&scope=repository:{repo}:pull"
    data = run("curl", "-fsSL", url, capture=True)
    return json.loads(data)["token"]


def docker_digest(repo: str, tag: str = "latest") -> str:
    token = docker_token(repo)
    headers = run(
        "curl",
        "-fsSI",
        "-H",
        f"Authorization: Bearer {token}",
        "-H",
        f"Accept: {ACCEPT}",
        f"https://registry-1.docker.io/v2/{repo}/manifests/{tag}",
        capture=True,
    )
    digest = ""
    for line in headers.splitlines():
        if line.lower().startswith("docker-content-digest:"):
            digest = line.split(":", 1)[1].strip()
            break
    if not DIGEST_RE.fullmatch(digest):
        raise SystemExit(f"invalid/missing Docker digest for {repo}:{tag}: {digest}")
    return digest


def build_lock(upstream_sha: str, langs: list[str]) -> str:
    lines = [f"upstream_ref {upstream_sha}"]
    for lang in langs:
        repo = f"codegolf/lang-{lang}"
        digest = docker_digest(repo)
        print(f"{lang}: {digest}")
        lines.append(f"lang_image {lang} {digest}")
    return "\n".join(lines) + "\n"


def sync_master(upstream_sha: str, dry_run: bool) -> None:
    print(f"Syncing master to {upstream_sha}")
    if dry_run:
        return
    run("git", "fetch", "--no-tags", "origin", "master")
    old_master = run("git", "rev-parse", "origin/master", capture=True)
    run(
        "git",
        "push",
        f"--force-with-lease=refs/heads/master:{old_master}",
        "origin",
        f"{upstream_sha}:refs/heads/master",
    )


def commit_lock(lock_text: str, dry_run: bool) -> None:
    old = LOCK_PATH.read_text() if LOCK_PATH.exists() else ""
    if old == lock_text:
        print("VERIFY_LOCK unchanged")
        return
    if dry_run:
        print("VERIFY_LOCK would change:")
        print(lock_text)
        return

    LOCK_PATH.write_text(lock_text)
    run("git", "add", "verify/VERIFY_LOCK")
    run("git", "diff", "--cached", "--check")
    run("git", "commit", "-m", "verify: rebuild verifier lock")
    run("git", "push", "origin", "HEAD:main")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream-ref", help="optional upstream commit/ref; defaults to upstream master")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    run("git", "config", "user.name", "github-actions[bot]")
    run("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")

    upstream_sha = resolve_upstream_ref(args.upstream_ref)
    langs = archived_languages()
    print(f"Archived languages: {len(langs)}")
    validate_languages_in_upstream(upstream_sha, langs)
    lock_text = build_lock(upstream_sha, langs)
    sync_master(upstream_sha, args.dry_run)
    commit_lock(lock_text, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
