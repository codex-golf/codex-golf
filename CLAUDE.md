# Maintainer Notes (for AI helpers)

Fork of `code-golf/code-golf`. Three branches with strict separation of concerns.

## Branches

- **`master`** — pure upstream mirror, byte-for-byte equal to `code-golf/code-golf:master`.

- **`main`** *(default)* — **our automation overlay**, based on a shared empty root commit:
  - `README.md`        — public-facing repo note
  - `CLAUDE.md`        — this file
  - `VERIFY_LOCK` — pinned upstream code and Docker language image digests
  - `verify/run.sh` and `verify/upstream-play.go` — thin verifier wrapper (called from solutions' workflow)
  - `.github/workflows/{merge-on-verify,leaderboard,reverify-all}.yml`
  - `scripts/`

  `main` does **not** carry `answers/` and does **not** carry the `pull_request` workflow trigger. When upstream code is needed, workflows read `VERIFY_LOCK` from `main`, checkout the pinned upstream-mirror commit, and pass that checkout to `verify/run.sh`. Do not use floating `master` for verification.

- **`solutions`** — **archived answers + verify trigger**, also based on the shared empty root commit:
  - `answers/<hole>/<lang>/<id>.<ext>` plus `<id>.meta.json`, `best`, and `index.json`
  - `.github/workflows/verify-pr.yml`        — thin trigger; checks out `main` for scripts and the upstream code pinned in `main/VERIFY_LOCK`

  PRs target this branch and still submit a staging `answers/<hole>/<lang>/answer.<ext>` file. Trusted merge converts that staging path into the archive layout. `solutions` should not carry verifier implementation files.

## Hard rules

0. **Minimize code changes.** Before adding new verifier/project logic, first look for the upstream code path and call it directly. Prefer a thin wrapper over reimplementing behavior.
1. **Always read project-local `CLAUDE.md` first** when working in a repo that has one. It is the project contract for agents.
2. **Follow Karpathy Guidelines for coding work.** Apply the behavioral rules from [`karpathy-guidelines`](https://github.com/forrestchang/andrej-karpathy-skills/blob/main/skills/karpathy-guidelines/SKILL.md): state assumptions, surface uncertainty, choose simplicity first, make surgical changes only, avoid speculative abstractions, and define verifiable success criteria before multi-step implementation.
3. **Never modify upstream files.** Anything that exists in upstream stays untouched on every branch unless Bond explicitly approves an upstream sync/conflict resolution.
4. **Disable upstream workflows via Settings**, not by editing their `.yml`.
5. **`master` carries no overlay.** Not even README/CLAUDE.
6. **`main` carries no `answers/` and no `pull_request` workflow.** It is not merged into `solutions`; `solutions` checks out `main` explicitly for scripts.
7. **`solutions` carries the workflow trigger and `answers/`** but its workflow body is just a thin shell that checks out `main`, reads `main/VERIFY_LOCK`, checks out the pinned upstream source commit, and calls `main/verify/run.sh`. No verifier logic on `solutions`.
8. PRs are opened against `solutions`.

## Re-syncing with upstream

`master` follows upstream. `main` and `solutions` are overlay branches based on
a shared empty root commit, not rebased onto latest `master`; this keeps PR diffs
and branch contents small while preserving GitHub's fork relationship.

```
git remote add upstream https://github.com/code-golf/code-golf.git
git fetch upstream

git checkout master && git merge --ff-only upstream/master
git push origin master

# Verification is pinned by main/VERIFY_LOCK. Advancing master alone must not
# change verifier behavior. To intentionally adopt new upstream judging code or
# language images, update VERIFY_LOCK on main, push main, then run Reverify all
# and the fork-PR harness before mass submissions.

# main/solutions are edited as overlays from the shared empty root commit.
# Do not merge latest master into them; workflows checkout the pinned
# VERIFY_LOCK commit whenever current upstream source is needed.
```

Open PRs against `solutions` should be based on the current `solutions` tip.

A manual workflow, **Sync upstream and rebuild lock**, performs the safe version
of this process: it syncs `master` to either a provided upstream commit/ref or
latest `code-golf/code-golf:master`, then rebuilds `VERIFY_LOCK` for the current
archived languages in `solutions`. If a specific upstream commit is supplied,
`master` is set to that upstream commit with `--force-with-lease` because
`master` is only a mirror. It intentionally does not pre-lock every upstream
language; each archived language adds one `lang_image` line.

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
- Hard-guard: PR must change exactly 1 file matching `^answers/<hole>/<lang>/answer\.<ext>$`, status A|M, commits ≤ 5; `verify/upstream-play.go` enforces upstream `/solution` parity (`code < 128KiB`) before calling `hole.Play()`
- Calls `main/verify/run.sh <hole> <lang> pr/<file> upstream`
- On success/failure: writes `verdict.json` (schema `codex-golf.verdict.v2`) and uploads as artifact
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
- Recomputes answer bytes/chars/sha256 from the PR head; verdict fields are hints, not authority
- Rejects exact duplicate sha256 entries; otherwise archives the answer even if it is not shorter than current best
- Labels (`verify-pass` / `verify-fail` / `archive-duplicate`) and posts comments
- On pass, creates a transformed merge commit: parents are current `solutions` and the PR head, while the tree stores archive layout (`<id>.<ext>`, `<id>.meta.json`, `best`, `index.json`) instead of the staging `answer.<ext>`
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
1. PR validation passes (single file, regex, commits)
2. Upstream parity guard accepts the code size (`<128KiB`), then official `hole.Play` returns pass for every generated run
3. Full sha256 is not already archived for that `(hole, lang)`
4. PR is still open, base is still `solutions`, and head sha still matches the verdict at merge time

## Adding a language

Do **not** add a local language registry to this overlay. Language support should
come from `master`:

- `master:config/data/langs.toml` is the source of truth for args/env and is
  consumed by upstream `hole.Play` / `run-lang`.
- `master:docker/live.Dockerfile` at the pinned upstream commit is the source of
  truth for which official language images exist. `VERIFY_LOCK` pins the
  immutable Docker digest for each accepted language; `verify/run.sh` pulls
  `codegolf/lang-<lang>@sha256:<digest>`, never floating `latest`.

If upstream adds a language and its official image is present in
`docker/live.Dockerfile`, the verifier should work after intentionally advancing
`VERIFY_LOCK` and adding the corresponding image digest there.
PR filenames still use the staging convention
`answers/<hole>/<lang>/answer.<ext>`; extension choice is repository convention,
not verifier logic.

## TODO / Roadmap

1. ~~**Multi-language**~~ — done. 87 langs (all upstream langs/ ∩ docker hub). End-to-end
   tested via PRs #1, #2, #3.
2. **Multi-answer storage** *(in progress)*.
   Goal: archive every verified, non-duplicate answer while keeping one clear
   best pointer per `(hole, lang)`.
   - Contributors still submit exactly one staging file:
     `answers/<hole>/<lang>/answer.<ext>`.
   - Trusted merge converts that staging file into archive files:
     `answers/<hole>/<lang>/<id>.<ext>`, `<id>.meta.json`, `best`, and
     `index.json`; `id = sha256(answer_bytes)[:16]`, with full sha256 in metadata.
   - Accept if official verification passes and the full sha256 is not already
     archived. Do **not** require the answer to beat current best.
   - Update `best` only when the new byte count is strictly smaller; otherwise
     archive the entry and leave `best` unchanged.
   - Use a transformed merge commit instead of plain `gh pr merge --squash`: the
     commit parents are current `solutions` and the PR head, but the tree stores
     the archive layout so `answer.<ext>` never lands on `solutions`.
   - `leaderboard.py` and `reverify-all.yml` read `index.json`/`best`, not
     `answer.<ext>` files. Recent entries come from metadata, not git log.
   - Migration uses `scripts/migrate_answers.py` to convert existing
     `answer.<ext>` files into archive entries with
     `source.kind = "legacy-single-answer-migration"`.
   - Before mass submissions resume: push both branch updates, run `Reverify all`,
     and pass the fork-PR harness against the new archive behavior.
3. **Leaderboard** — see `main/scripts/leaderboard.py` and `.github/workflows/leaderboard.yml`.
   - Scans `solutions/answers/*/*/index.json` and `best`, emits `LEADERBOARD.md`
     on `solutions` with:
     - Best-by-hole table: lang × bytes × entry id
     - Best-by-lang table: hole × bytes × entry id
     - Recent accepted entries from metadata `merged_at`
   - Scheduled daily; manually re-runnable via `workflow_dispatch`.
4. **Periodic full re-run** — see `.github/workflows/reverify-all.yml`.
   - Runs weekly on `main`. Re-verifies every archived entry listed in
     `answers/<hole>/<lang>/index.json` using the same `verify/run.sh`.
   - Catches: upstream changing expected output, lang image regressions, our
     verifier breaking against an existing entry.
   - On regression: posts an issue with the failing entries; does **not**
     auto-evict (manual decision: do we follow upstream change, or open a PR
     against upstream?).
5. **Manual upstream/runtime lock refresh** — see `.github/workflows/sync-upstream-lock.yml`.
   - `workflow_dispatch` input `upstream_ref` is optional. Empty means latest
     upstream `master`; a supplied value may be a specific upstream commit/ref.
   - The workflow syncs `master` first (`--force-with-lease` when setting it to
     an explicit upstream commit), then rebuilds compact `VERIFY_LOCK` from
     current `solutions` archive languages and Docker Hub image digests.
   - After it changes `VERIFY_LOCK`, run `Reverify all` and the fork harness
     before mass submissions resume.
6. ~~**Slim overlay branches**~~ — done.
   - `main` and `solutions` are based on a shared empty root commit instead of latest `master`.
   - `master` remains the current upstream mirror.
   - Actions checkout `master` separately whenever upstream code is needed; `verify/run.sh` builds official `run-lang.c` and `hole.Play()` from that checkout while using this overlay's tiny wrapper and language registry.
7. **Reusable fork-PR action test harness** — see `scripts/fork_pr_harness.py`.
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
