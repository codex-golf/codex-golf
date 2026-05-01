# Maintainer Notes (for AI helpers)

Fork of `code-golf/code-golf`. Three branches with strict separation of concerns.

## Branches

- **`master`** — pure upstream mirror, byte-for-byte equal to `code-golf/code-golf:master`.

- **`main`** *(default)* — **our automation overlay**, based on a shared empty root commit:
  - `README.md`        — public-facing repo note
  - `CLAUDE.md`        — this file
  - `verify/run.sh`    — verifier runner (called from solutions' workflow)
  - `verify/langs.json` and `verify/upstream-play.go`
  - `.github/workflows/{merge-on-verify,leaderboard,reverify-all}.yml`
  - `scripts/`

  `main` does **not** carry `answers/` and does **not** carry the `pull_request` workflow trigger. When upstream code is needed, workflows checkout `master` separately and pass that checkout to `verify/run.sh`.

- **`solutions`** — **answers + verify trigger**, also based on the shared empty root commit:
  - `answers/<hole>/<lang>/answer.<ext>`     — submitted solutions
  - `.github/workflows/verify-pr.yml`        — thin trigger; checks out `main` for scripts and `master` for upstream code

  PRs target this branch. `solutions` should not carry verifier implementation files.

## Hard rules

0. **Minimize code changes.** Before adding new verifier/project logic, first look for the upstream code path and call it directly. Prefer a thin wrapper over reimplementing behavior.
1. **Always read project-local `CLAUDE.md` first** when working in a repo that has one. It is the project contract for agents.
2. **Never modify upstream files.** Anything that exists in upstream stays untouched on every branch unless Bond explicitly approves an upstream sync/conflict resolution.
3. **Disable upstream workflows via Settings**, not by editing their `.yml`.
4. **`master` carries no overlay.** Not even README/CLAUDE.
5. **`main` carries no `answers/` and no `pull_request` workflow.** It is not merged into `solutions`; `solutions` checks out `main` explicitly for scripts.
6. **`solutions` carries the workflow trigger and `answers/`** but its workflow body is just a thin shell that checks out `main`, checks out `master` as upstream source, and calls `main/verify/run.sh`. No verifier logic on `solutions`.
7. PRs are opened against `solutions`.

## Re-syncing with upstream

`master` follows upstream. `main` and `solutions` are overlay branches based on
a shared empty root commit, not rebased onto latest `master`; this keeps PR diffs
and branch contents small while preserving GitHub's fork relationship.

```
git remote add upstream https://github.com/code-golf/code-golf.git
git fetch upstream

git checkout master && git merge --ff-only upstream/master
git push origin master

# main/solutions are edited as overlays from the shared empty root commit.
# Do not merge latest master into them; workflows checkout master separately
# whenever current upstream source is needed.
```

Open PRs against `solutions` should be based on the current `solutions` tip.

## Recreating this repository from scratch

Use this when we want a clean trunk after failed/noisy PR experiments: delete
and rebuild the public repo so closed/failed PRs and their review/edit history no
longer clutter the project. The rebuild must still preserve GitHub's **forked
from `code-golf/code-golf`** relationship while keeping our branches slim.

1. **Fork upstream into the org, default branch only, then rename.**
   - Prefer a default-branch-only fork so upstream topic branches do not appear
     in our repo.
   - The successful manual path was: create the org fork as
     `codex-golf/code-golf`, then rename it to `codex-golf/codex-golf`.
   - Verify with the GitHub API that the rebuilt repo has:
     `fork: true`, `parent: code-golf/code-golf`, `source: code-golf/code-golf`.

   ```sh
   gh api -X POST repos/code-golf/code-golf/forks \
     -f organization=codex-golf \
     -F default_branch_only=true

   gh api -X PATCH repos/codex-golf/code-golf \
     -f name=codex-golf

   gh api repos/codex-golf/codex-golf \
     --jq '{full_name,fork,parent:(.parent.full_name // null),source:(.source.full_name // null),default_branch}'
   ```

2. **Activate Actions and restrict allowed actions.**
   - Keep only GitHub-owned actions / explicit `actions/*` patterns we use.
   - Enable issues too; `reverify-all.yml` opens regression issues.
   - If old upstream workflows appear, disable them in Settings/API; do not edit
     upstream workflow files on `master`.

   ```sh
   gh api --method PATCH repos/codex-golf/codex-golf \
     -F has_issues=true

   printf '%s\n' '{"enabled":true,"allowed_actions":"selected"}' \
     | gh api --method PUT repos/codex-golf/codex-golf/actions/permissions --input -

   printf '%s\n' '{"github_owned_allowed":true,"verified_allowed":false,"patterns_allowed":["actions/checkout@*","actions/upload-artifact@*","actions/download-artifact@*"]}' \
     | gh api --method PUT repos/codex-golf/codex-golf/actions/permissions/selected-actions --input -
   ```

3. **Push the three semantic branches.**
   - `master` is exactly upstream `master`.
   - `main` and `solutions` are based on a shared empty root commit, not latest
     `master`. This is the deliberate slim-overlay design: workflows checkout
     `master` separately when current upstream code is needed.
   - Do **not** merge `master` into `main` or `solutions`.

   ```sh
   git fetch upstream master
   git checkout -B master upstream/master
   git push --force origin master:master

   git checkout --orphan empty-base
   git rm -rf . || true
   git commit --allow-empty -m 'empty base'
   EMPTY=$(git rev-parse HEAD)

   git checkout -B main "$EMPTY"
   # add only: README.md, LICENSE, CLAUDE.md, verify/, scripts/,
   # .github/workflows/{merge-on-verify,leaderboard,reverify-all}.yml
   git commit -m 'main branch: automation overlay on empty base'
   git push --force origin main:main

   git checkout -B solutions "$EMPTY"
   # add only: answers/, LEADERBOARD.md, and .github/workflows/verify-pr.yml
   git commit -m 'solutions branch: answers and verify trigger on empty base'
   git push --force origin solutions:solutions
   ```

4. **Set public repo identity.**
   - `README.md` on `main` is part manifesto, part operating guide: the project
     criticizes the use of open-source code golf as a closed personal show-off
     scoreboard, thanks the upstream maintainers for their open-source work and
     MIT license, embraces AI participation, and frames code golf as a shared
     human+AI race.
   - `LICENSE` on `main` must preserve the upstream MIT notice and cover the
     automation overlay.
   - Do not criticize sponsor-only Solution Notes as shared/paywalled knowledge:
     source review shows notes are per-user personal notes, not sponsor-shared
     notes. If discussing trust, frame it instead as the structural asymmetry of
     closed submissions: the judging server can see answers while the public
     cannot.
   - Set the GitHub description and topics to match that public identity. Keep
     the wording principled; do not name or attack individual players.

   ```sh
   gh repo edit codex-golf/codex-golf \
     --description "Human + AI code-golf archive — open solutions, verified runs, every step recorded." \
     --homepage "https://github.com/codex-golf/codex-golf" \
     --add-topic code-golf,ai,open-source,human-ai,solutions,archive
   ```

5. **Set `main` as default and clean branches.**
   - Set default branch to `main` after pushing it.
   - Keep only `main`, `master`, and `solutions`; delete inherited upstream topic
     branches or old PR/test branches.

   ```sh
   gh api -X PATCH repos/codex-golf/codex-golf -f default_branch=main

   git ls-remote --heads origin | sed 's#refs/heads/##' | while read -r _ branch; do
     case "$branch" in main|master|solutions) ;; *) git push origin ":$branch" ;; esac
   done
   ```

6. **Register/verify workflows.**
   - After `main` is the default branch, GitHub should show only our active
     workflows: `Leaderboard`, `Merge on Verify`, and `Reverify all`.
   - Run `Reverify all` once and trigger `Leaderboard` once. Both should pass.
   - Final sanity checks:
     - repo is still a fork of `code-golf/code-golf`;
     - branch list is exactly `main`, `master`, `solutions`;
     - `master == upstream/master`;
     - `main` and `solutions` share the same empty root commit and remain only
       a small number of overlay commits ahead of it.

## Verify workflow contract

Two workflows, **untrusted/trusted split** to handle fork PRs whose
`GITHUB_TOKEN` is read-only:

### `solutions/.github/workflows/verify-pr.yml` — untrusted side

- Trigger: `pull_request` to `solutions` touching `answers/**`
- Permissions: read-only (`contents: read`, `pull-requests: read`)
- Three checkouts: `pr/` (PR head, untrusted), `main/` (verifier scripts), `upstream/` (upstream master with `config/hole-answers/`)
- Hard-guard: PR must change exactly 1 file matching `^answers/<hole>/<lang>/answer\.<ext>$`, status A|M, commits ≤ 5, size ≤ 16384B
- Calls `main/verify/run.sh <hole> <lang> pr/<file> upstream`
- On success/failure: writes `verdict.json` (schema `codex-golf.verdict.v1`) and uploads as artifact
- **Does not** label / comment / merge — fork tokens can't, and we don't trust this side anyway

### `main/.github/workflows/merge-on-verify.yml` — trusted side

- Trigger: `workflow_run` on "Verify PR" `completed`
- **Always runs from `main` default branch** — PRs cannot tamper with this yaml
- Permissions: `contents: write`, `pull-requests: write`, `issues: write`
- Downloads verdict.json artifact via `actions/download-artifact@v4` with the triggering `run-id`
- Re-validates **everything** against ground truth from GitHub API:
  - PR is open, base ref == `solutions`
  - PR head sha matches verdict head sha
  - Verify workflow conclusion was `success` AND verdict status is `pass`
- Race-safe re-check: fetch current file on `solutions` via Contents API, ensure new bytes < current best
- Labels (`verify-pass` / `verify-fail`), posts comment, `gh pr merge --squash` on pass
- Concurrency: `merge-on-verify` (global serial) to avoid races on `solutions`

### Official runner wrapper (in `verify/run.sh`)

- Do **not** reimplement code.golf judging semantics in shell.
- `verify/run.sh` prepares the official execution layout for the submitted language:
  - compiles upstream `run-lang.c` to `/usr/bin/run-lang`
  - exports `codegolf/lang-<lang>` into `/langs/<lang>/rootfs`
  - creates `/run_root` and a dummy `/lang-digests.json` for config init
- Then it builds/runs `verify/upstream-play.go`, a tiny wrapper around upstream `hole.Play(ctx, hole, lang, code)`.
- Official `hole.Play` owns args/stdin/env, per-language quirks, output trimming, timeout, exit-code handling, and hole judges.

### Auto-merge gates

All must hold:
1. PR validation passes (single file, regex, size, commits)
2. Official `hole.Play` returns pass for every generated run
3. New bytes < current best on `origin/solutions` (re-checked twice: once during verify, once in merger)
4. PR is still open and base is still `solutions` at merge time

## Adding a language

Edit `verify/langs.json` on `main`:
```json
"<lang>": { "ext": "<ext>", "image": "codegolf/lang-<lang>:latest" }
```

Upstream maintains pre-built docker images at `codegolf/lang-<lang>` on Docker
Hub. The verifier exports the selected image as the official `/langs/<lang>/rootfs`
and lets upstream `hole.Play` / `run-lang` decide how to execute it.

Languages without an official docker image (currently:
`arkscript / knight / lily / luau / qore / stax / umka / vala`) are skipped
— we'd have to either build & push our own image or skip the lang.

Extension convention:
- Industry-standard where unambiguous: `.py / .rs / .js / .rb / .java / ...`
- Lang name as fallback for esolangs: `.bqn / .uiua / .5ab1e`
- Explicit overrides to avoid collisions: `forth=.fth` (vs f-sharp's `.fs`),
  `prolog=.prolog` (vs perl's `.pl`)

Then merge `main` → `solutions`. The new lang is live for the next PR.

## TODO / Roadmap

1. ~~**Multi-language**~~ — done. 87 langs (all upstream langs/ ∩ docker hub). End-to-end
   tested via PRs #1, #2, #3.
2. **Multi-answer storage** *(deferred, design only)*. Currently we keep one
   answer per `(hole, lang)`: the shortest. Future plan to store every PASS and
   celebrate every improvement, not just the final best:
   - PRs still submit `answers/<hole>/<lang>/answer.<ext>` for simple review.
   - At trusted merge time, the merger renames the submitted answer to a stable
     content-addressed file: `answers/<hole>/<lang>/<sha>.<ext>` (sha = content
     sha-256 first 12+ chars). This prevents duplicates and merge conflicts.
   - Store metadata next to the answer as `answers/<hole>/<lang>/<sha>.<ext>.md`
     (or equivalent structured sidecar if we later need machine parsing). Include:
     `author`, `submitted_at`, `merged_at`, `pr`, `commit`, `bytes`, `chars`,
     `sha256`, `was_best`, `previous_best_sha`, `previous_best_bytes`,
     `previous_best_chars`, `improvement_bytes`, `improvement_chars`, and the
     repository best bytes/chars at submission time.
   - Pointer: `answers/<hole>/<lang>/best` contains the current shortest sha;
     optional `answers/<hole>/<lang>/index.json` can list all accepted entries
     for leaderboard/history generation.
   - Verifier accepts a new answer if it (a) passes verify and either
     (b₁) is shorter than current `best`, or (b₂) is within an accepted archive
     window and not byte-equal to an existing entry. The exact archive window is
     a policy decision; do not make it too broad until storage/UI is ready.
   - Merger must update `best` only when the new answer improves bytes/chars,
     but it may still archive non-best accepted entries for diversity/history.
   - Migration: existing `answer.<ext>` becomes `<sha>.<ext>` + `<sha>.<ext>.md`
     + `best` pointer.
   - **Not implemented yet** — needs merger rewrite and leaderboard/reverify
     updates. Keep the current one-PR/one-shortest-improvement model until the
     fork-PR harness can safely test this merge-time rename behavior.
3. **Leaderboard** — see `main/scripts/leaderboard.py` and `.github/workflows/leaderboard.yml`.
   - Scans `solutions/answers/`, emits `LEADERBOARD.md` on `solutions` with:
     - Per-hole table: lang × bytes (sorted)
     - Per-lang table: hole × bytes (sorted)
     - Recent submissions feed (last 30 commits to solutions touching `answers/`)
   - Scheduled daily; manually re-runnable via `workflow_dispatch`.
4. **Periodic full re-run** — see `.github/workflows/reverify-all.yml`.
   - Runs weekly on `main`. Re-verifies every `answers/<hole>/<lang>/answer.<ext>`
     against current upstream `config/hole-answers/<hole>.txt` using the same
     `verify/run.sh`.
   - Catches: upstream changing expected output, lang image regressions, our
     verifier breaking against an existing entry.
   - On regression: posts an issue with the failing entries; does **not**
     auto-evict (manual decision: do we follow upstream change, or open a PR
     against upstream?).
5. ~~**Slim overlay branches**~~ — done.
   - `main` and `solutions` are based on a shared empty root commit instead of latest `master`.
   - `master` remains the current upstream mirror.
   - Actions checkout `master` separately whenever upstream code is needed; `verify/run.sh` builds official `run-lang.c` and `hole.Play()` from that checkout while using this overlay's tiny wrapper and language registry.
6. **Reusable fork-PR action test harness** — see `scripts/fork_pr_harness.py`.
   - Simulates the real outside contributor flow: fork repo → push answer branch
     to the fork → open PR from fork into `codex-golf/codex-golf:solutions` →
     wait for `Verify PR` → wait for `Merge on Verify` → assert
     labels/comments/merge state/solution bytes.
   - Do **not** use extra throwaway branches in the base repo for this test
     path; keep `codex-golf/codex-golf` branches clean. Use an explicit fork
     owner via `--fork-owner`; the script can refuse blocked owners configured
     via `CODEX_GOLF_BLOCKED_FORK_OWNERS` and never silently uses the active gh
     account.
   - Current implemented cases: `fail-05ab1e` (safe default, expected verify
     failure and no solutions mutation) and `pass-basic` (requires
     `--allow-merge` because it mutates `solutions`).
   - Safety gates: test PR titles/bodies/comments/commits must use generic text
     only; never mention private/source identity strings. Clean up test fork
     branches and close failed test PRs unless intentionally kept for diagnosis.
   - E2E result: `fail-05ab1e` passed using `heshenclaw/codex-golf-e2e` → PR
     #34 got `verify-fail`, was closed, and the fork branch was deleted.
   - Acceptance criterion: every verifier/merger architecture change must pass
     this fork-PR harness before mass submissions resume.
