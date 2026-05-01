# Maintainer Notes for AI Helpers

`codex-golf/codex-golf` is a fork of `code-golf/code-golf` with a small automation overlay and an open answer archive.

## Non-negotiables

1. Read this file before coding in this repo.
2. Make the smallest working change. Prefer thin wrappers around upstream code over reimplementation.
3. Do not edit upstream files or upstream workflow files unless Bond explicitly approves it.
4. Keep public GitHub text generic. Do not mention private/source identities in PR titles, bodies, comments, commits, issues, or generated pages.
5. Run end-to-end validation. Do not trust code reading alone.
6. Follow Karpathy-style coding discipline: state assumptions, surface uncertainty, choose simple/surgical changes, avoid speculative abstractions, define verifiable success criteria.

## Branch contract

- `master`
  - Pure mirror of `code-golf/code-golf:master`.
  - No overlay files. Do not merge overlay work into it.

- `main` *(default)*
  - Automation overlay only, based on the shared empty root commit.
  - Contains: `README.md`, `LICENSE`, `CLAUDE.md`, `verify/`, `scripts/`, `tests/functional/`, and workflows:
    - `merge-on-verify.yml`
    - `reverify-all.yml`
    - `sync-upstream-lock.yml`
    - `verify-issue.yml`
  - Does **not** contain `answers/`.
  - Does **not** contain the `pull_request` verify trigger.

- `solutions`
  - Answer archive plus the thin PR trigger, also based on the shared empty root commit.
  - Contains:
    - `answers/`
    - `.github/workflows/verify-pr.yml`
  - Does **not** contain verifier implementation files.

Never merge/rebase `master` into `main` or `solutions`. Workflows checkout pinned upstream source separately.

## Verifier lock

`main:verify/VERIFY_LOCK` is the single verifier lock.

It pins:
- `upstream_ref <40-hex-sha>`
- `lang_image <lang> sha256:<digest>` for each archived language

Verification must read `main/verify/VERIFY_LOCK`; do not use floating `master` or floating Docker `latest` during normal verification.

To intentionally update upstream source/runtime images, use the manual workflow **Sync upstream and rebuild lock**, then run **Reverify all** and the fork PR harness before mass submissions.

## Verify architecture

### Untrusted side: `solutions/.github/workflows/verify-pr.yml`

Triggered by PRs to `solutions` touching `answers/**`.

Guards:
- exactly one changed file
- path must be `answers/<hole>/<lang>/answer.<ext>`
- file status A/M
- at most 5 commits
- answer size parity: `<128KiB`

Flow:
1. Checkout PR head as untrusted input.
2. Checkout `main` for scripts.
3. Read `main/verify/VERIFY_LOCK` and checkout pinned upstream source.
4. Run `main/verify/run.sh <hole> <lang> pr/<file> upstream`.
5. Upload `verdict.json` artifact with schema `codex-golf.verdict.v2`.

This workflow is read-only. It must not label, comment, or merge.

### Trusted side: `main/.github/workflows/merge-on-verify.yml`

Triggered by `workflow_run` for `Verify PR`.

Flow:
1. Download verdict artifact.
2. Re-validate against GitHub API ground truth:
   - PR is open
   - base is `solutions`
   - PR head sha matches verdict
   - verify run succeeded and verdict status is `pass`
3. Recompute answer bytes/chars/sha256 from PR head.
4. Reject exact duplicate sha256 for that `(hole, lang)`.
5. Archive accepted answers with a transformed merge commit.
6. Apply labels/comments.

Concurrency group: `merge-on-verify` to serialize writes to `solutions`.

## Official runner wrapper

`verify/run.sh` prepares the upstream execution layout and calls the tiny Go wrapper in `verify/upstream-play.go`.

Key points:
- compile upstream `run-lang.c` to `/usr/bin/run-lang`
- export pinned `codegolf/lang-<lang>@sha256:<digest>` into `/langs/<lang>/rootfs`
- create `/run_root` and dummy `/lang-digests.json`
- build/run `verify/upstream-play.go`
- `upstream-play.go` calls upstream `hole.Play(ctx, hole, lang, code)`

Do not clone judge semantics into shell or Python. Upstream `hole.Play` owns args/stdin/env, language quirks, trimming, timeout, exit handling, and hole judges.

## Archive layout

Contributors submit staging files only:

```text
answers/<hole>/<lang>/answer.<ext>
```

Trusted merge archives them as:

```text
answers/<hole>/<lang>/<id>.<ext>
answers/<hole>/<lang>/<id>.meta.json
answers/<hole>/<lang>/best
answers/<hole>/<lang>/index.json
```

Where:
- `id = sha256(answer_bytes)[:16]`
- full sha256 is stored in metadata/index
- exact duplicate full sha256 is rejected
- verified non-duplicates are archived even if longer than current best
- `best` updates only on strictly smaller byte count

`answers/index.js` is the lightweight root client manifest. It is maintained by `scripts/archive_merge.py` and points to per-hole/per-language indexes. Do not reintroduce generated Markdown leaderboard files.

## Scripts and tests

- `scripts/` — workflow/runtime/maintenance scripts used by Actions.
- `tests/functional/` — manual E2E/functional harnesses.

Current important scripts:
- `scripts/archive_merge.py`
- `scripts/issue_submission.py`
- `scripts/reverify_archive.py`
- `scripts/rebuild_verify_lock.py`
- `tests/functional/fork_pr_harness.py`

Fork harness rules:
- use a real fork, not base-repo throwaway branches
- require explicit `--fork-owner`
- do not use blocked owners
- pass cases require `--allow-merge`
- keep PR-visible text generic
- delete test branches after runs

Run the fork harness after verifier/merger architecture changes and before mass submissions.

## Common validation commands

```sh
# main checkout
python3 -m py_compile scripts/archive_merge.py scripts/reverify_archive.py scripts/rebuild_verify_lock.py tests/functional/fork_pr_harness.py
bash -n verify/run.sh
ruby /tmp/validate_codex_yaml.rb .github/workflows/*.yml
python3 scripts/rebuild_verify_lock.py --dry-run

# solutions checkout
ruby /tmp/validate_codex_yaml.rb .github/workflows/verify-pr.yml
```

Useful live validations:

```sh
gh workflow run "Reverify all" --repo codex-golf/codex-golf --ref main
gh workflow run sync-upstream-lock.yml --repo codex-golf/codex-golf --ref main
CODEX_GOLF_BLOCKED_FORK_OWNERS=jusaka \
  python3 tests/functional/fork_pr_harness.py \
  --fork-owner heshenclaw \
  --case pass-python-leap-years \
  --corpus <local-corpus-root> \
  --allow-merge
```

## Upstream/runtime sync

Preferred path: run **Sync upstream and rebuild lock**.

Manual equivalent:
1. Fetch selected `code-golf/code-golf` upstream ref.
2. Set `master` to that upstream commit because `master` is mirror-only.
3. Rebuild `verify/VERIFY_LOCK` for languages currently archived in `solutions`.
4. Push `main` if the lock changed.
5. Run **Reverify all**.
6. Run the fork harness.

Do not pre-lock all upstream languages; add image digest lines only for languages present in the archive.

## Rebuilding the public repo

Only for deliberate cleanup after noisy/failed PR experiments.

Requirements:
- preserve GitHub fork relationship to `code-golf/code-golf`
- default branch: `main`
- branch list: exactly `main`, `master`, `solutions`
- `master` equals upstream mirror
- `main` and `solutions` share the same empty root commit
- active workflows visible on GitHub:
  - `Merge on Verify`
  - `Reverify all`
  - `Sync upstream and rebuild lock`

Public identity:
- respect upstream maintainers and MIT license
- frame critique as closed-submission trust asymmetry, not misconduct
- do not claim sponsor Solution Notes are shared/paywalled knowledge; source shows they are per-user notes
- keep wording principled; do not name or attack individual players

## Issue submission queue

Preferred public submission path is an Issue labeled by an authorized maintainer.

Issue form fields:
- `Hole` — code.golf hole id, for example `fizz-buzz`
- `Language` — code.golf language id, for example `python`
- `Answer code` — the code to verify
- `Notes` — optional reviewer context; do not archive notes into the repository

Flow:
- User opens issue with the **Answer submission** issue template.
- Authorized maintainer applies `verify-request`.
- `verify-issue.yml` parses the issue, computes bytes/sha256, derives the archive file extension from language id, verifies with `verify/run.sh`, and archives via `scripts/issue_submission.py`.
- Archive writes use optimistic push retry against latest `origin/solutions`; concurrent accepted issues should all eventually land.
- Successful or duplicate submissions are labeled/commented and closed.

## Current TODO

- Add an issue-submission E2E harness.
- Extend `tests/functional/fork_pr_harness.py` for:
  - duplicate exact-content
  - valid longer non-best archive
  - future new-best
  - race/concurrency behavior
- Run fork harness after any verifier/merger change.
- Rotate heavily used personal GitHub tokens when convenient.
