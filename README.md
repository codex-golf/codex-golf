# codex-golf — Open Code Golf Solutions Archive

**Verified code golf answers, open solution history, and reproducible human + AI golfing experiments.**

[![Verify Issue Submission](https://github.com/codex-golf/codex-golf/actions/workflows/verify-issue.yml/badge.svg?branch=main)](https://github.com/codex-golf/codex-golf/actions/workflows/verify-issue.yml)
[![Reverify all](https://github.com/codex-golf/codex-golf/actions/workflows/reverify-all.yml/badge.svg?branch=main)](https://github.com/codex-golf/codex-golf/actions/workflows/reverify-all.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

`codex-golf` is a public archive for **code golf solutions**: short programs,
byte-saving tricks, verifier tooling, and answer history for the
[`code.golf`](https://code.golf/) ecosystem. It is built for people and agents
who want to study how solutions improve over time, reproduce verification, and
submit new answers through an open process.

## Why this repository exists

Code golf is more useful when the path to an answer is visible. A final byte
count is only the headline; the real value is in the language quirks,
intermediate attempts, verifier details, and small discoveries that lead there.

This repository keeps those pieces public:

- **Open solutions** — accepted answers are archived in Git instead of hidden in
  a private submission box.
- **Reproducible verification** — answers are checked with a thin wrapper around
  upstream `hole.Play()` and pinned language runtimes.
- **Human + AI friendly workflow** — both human golfers and AI coding agents can
  submit answers, compare approaches, and learn from the archive.
- **Every accepted answer matters** — non-best verified answers are still stored
  as part of the solution history; `best` updates only when byte count improves.

We are not trying to replace the shared code.golf leaderboard. The goal is an
open notebook: a searchable record of code golf ideas, verified runs, and answer
provenance.

## What you can do here

- Browse archived solutions on the [`solutions`](../../tree/solutions/answers)
  branch.
- Submit a new code golf answer with the **Answer submission** issue template.
- Inspect the verifier and archive automation on `main`.
- Reproduce archive checks through GitHub Actions.
- Study human and AI code golf techniques across languages.

Useful keywords for explorers: **code golf solutions**, **AI code golf**,
**verified programming puzzles**, **esolang golfing**, **reproducible judges**,
**open source leaderboard archive**, and **shortest code examples**.

## Submit an answer

Open an issue using the **Answer submission** template. Required fields are:

- hole id, for example `fizz-buzz`
- language id, for example `python`
- file extension, for example `py`
- answer code

Notes are optional and stay on the issue only; they are not archived into this
repository. The workflow computes bytes and sha256 automatically.

A maintainer can apply the `verify-request` label to run the official verifier.
Passing submissions are archived on the `solutions` branch; exact duplicates are
reported and closed without changing the archive.

## How verification works

The verifier intentionally stays small. It does **not** clone judging semantics
into this repository.

1. `main:verify/VERIFY_LOCK` pins the upstream source commit and language Docker
   image digests.
2. The workflow checks out the pinned upstream source.
3. `verify/run.sh` prepares the official runner layout (`/usr/bin/run-lang`,
   `/langs/<lang>/rootfs`, `/run_root`).
4. A tiny Go wrapper calls upstream `hole.Play(ctx, hole, lang, code)`.
5. Passing answers are written to the archive with content-addressed ids.

That keeps the archive close to official behavior while still making the process
inspectable and reproducible.

## Repository layout

This repository is a fork of [`code-golf/code-golf`](https://github.com/code-golf/code-golf)
with a small automation overlay for accepting and verifying solutions.

Branches:

- `master`: upstream mirror.
- `main`: verifier, issue workflow, archive tooling, project docs, and
  maintainer automation.
- `solutions`: accepted answers and archive indexes.

Important paths:

- [`verify/`](verify/) — thin official-runner wrapper and verifier lock.
- [`scripts/`](scripts/) — archive, reverify, and submission automation.
- [`answers/`](../../tree/solutions/answers) — archived solutions on the
  `solutions` branch.
- [`CLAUDE.md`](CLAUDE.md) — maintainer notes for AI helpers and contributors.

## Archive policy

Accepted answers are stored as:

```text
answers/<hole>/<lang>/<id>.<ext>
answers/<hole>/<lang>/<id>.meta.json
answers/<hole>/<lang>/best
answers/<hole>/<lang>/index.json
```

Where `id` is derived from `sha256(answer_bytes)`. Exact duplicate answers are
reported without changing the archive. Verified non-duplicates are preserved even
when they are longer than the current best answer.

## Respect for upstream

This project exists because `code-golf/code-golf` is open source. We are grateful
to James Raspass and the code.golf contributors for building the platform and
releasing it under the MIT License.

Our focus is transparency, reproducibility, and shared learning. This fork keeps
its automation separate from the upstream mirror and preserves the upstream
license notice.

## License

This fork and its automation overlay are released under the MIT License. The
upstream copyright notice is preserved in [`LICENSE`](LICENSE).
