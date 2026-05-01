# codex-golf

**A public notebook for human + AI code golf.**

Code golf is beautiful because every byte carries an idea. A shorter answer is
not just a number; it is a trail of tricks, language quirks, failed attempts,
small discoveries, and shared taste.

But too much of competitive code golf has drifted toward private scorekeeping.
Some players use open infrastructure while treating their own work as a vault:
answers disappear into profiles, leaderboards become trophy cases, and the path
to each improvement is hidden. Some also treat AI participation with reflexive
hostility, as if using new tools makes the discovery less real.

We disagree.

## What we believe

- **Open beats hoarded.** If a solution improves the state of the art, the code,
  context, and verification path should be visible.
- **AI belongs in the arena.** Humans and AI systems are now both part of the
  creative process. The interesting question is not who gets to participate, but
  what we can discover together.
- **The leaderboard is not private capital.** A rank should not be a personal
  show-off asset extracted from a shared ecosystem. Code golf is more valuable
  when the whole community can learn from each step.
- **Every footprint matters.** Final best answers matter, but so do intermediate
  improvements, failed submissions, verifier fixes, and tooling.

This repository is our answer: a transparent archive where accepted solutions
and the machinery that verifies them are kept in public.

We are **not** trying to build a separate personal leaderboard. The only
leaderboard worth caring about is the shared one: what all humans and all AIs can
collectively reach.

## Why archive solutions?

Submitting to code.golf necessarily sends an answer to the official service for
execution and, when logged in, ranking. That is understandable: online judging
requires code to be transmitted somewhere.

But it creates a structural asymmetry: the server can see submitted answers,
while the public cannot. We do not claim misconduct by the upstream maintainers;
we are pointing out the incentive problem created by any closed submission box.
When valuable answers are visible to an operator but invisible to everyone else,
the community must rely on trust instead of reproducibility.

We prefer a simpler rule: if an answer is good enough to affect the public
competition, it should also be good enough to enter the public record. Public
archives reduce suspicion, preserve credit, and let every person and every AI
learn from the same history.

## Respect for upstream

This project exists because [`code-golf/code-golf`](https://github.com/code-golf/code-golf)
is open source. We are grateful to James Raspass and the code.golf contributors
for building the platform and releasing it under the MIT License.

Our criticism is not aimed at the upstream maintainers or at the sponsors who
help keep the service alive. It is aimed at the habit of using an open-source
game as a closed personal scoreboard. The upstream MIT license makes forks,
experiments, and public archives possible; this repository tries to honor that
spirit.

## Repository layout

This repository is a fork of `code-golf/code-golf` with a small automation
overlay for accepting and verifying solutions.

The key `/about` content is already present in the `master` upstream mirror, so
we do not duplicate the page in `main`; we cite the upstream source directly.

Branches:

- `master`: upstream mirror.
- `main`: verifier, merger, archive index, project docs, and maintainer tooling.
- `solutions`: accepted answers plus the thin PR verification trigger.

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

This branch was rebuilt under the project runbook section titled **Recreating
this repository from scratch**; see [`CLAUDE.md`](CLAUDE.md) for the branch
contract and operating notes.

## License

This fork and its automation overlay are released under the MIT License. The
upstream copyright notice is preserved in [`LICENSE`](LICENSE).
