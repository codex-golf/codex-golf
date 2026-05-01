#!/usr/bin/env bash
# Usage: verify/run.sh <hole> <lang> <answer-file> <upstream-checkout>
# Prints "PASS <bytes>" on success, exits non-zero on failure.
#
# Minimal verifier wrapper: do not reimplement code.golf judging semantics here.
# Build a tiny Go CLI that calls upstream hole.Play(), and provide the official
# run-lang sandbox layout (/usr/bin/run-lang + /langs/<lang>/rootfs).
set -euo pipefail

HOLE="$1"; LANG="$2"; SOL="$3"; UPSTREAM="${4:-.}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UPSTREAM_ROOT="$(cd "$UPSTREAM" && pwd)"
LOCK="$ROOT/LANG_IMAGE_LOCK.json"

[ -f "$SOL" ] || { echo "::error::no solution file: $SOL"; exit 1; }
[ -f "$LOCK" ] || { echo "::error::missing language image lock: $LOCK"; exit 1; }
case "$LANG" in
  *[!a-z0-9-]*|'') echo "::error::invalid language id: $LANG"; exit 1 ;;
esac

LOCK_UPSTREAM_REF="$(jq -r '.upstream_ref // empty' "$LOCK")"
ACTUAL_UPSTREAM_REF="$(git -C "$UPSTREAM_ROOT" rev-parse HEAD)"
if [ "$LOCK_UPSTREAM_REF" != "$ACTUAL_UPSTREAM_REF" ]; then
  echo "::error::LANG_IMAGE_LOCK.json upstream_ref ($LOCK_UPSTREAM_REF) does not match checked-out upstream ($ACTUAL_UPSTREAM_REF)"
  exit 1
fi

# Do not maintain a parallel args/env registry in this overlay. Upstream's
# config/data/langs.toml still drives hole.Play()/run-lang execution. The only
# local registry is an immutable Docker digest lock, so code and language
# rootfs versions move only when main explicitly updates both locks.
if ! grep -Eq "^[[:space:]]*COPY --from=codegolf/lang-${LANG}[[:space:]]" "$UPSTREAM_ROOT/docker/live.Dockerfile"; then
  echo "::error::unsupported lang or missing official image in pinned upstream: $LANG"
  exit 1
fi
IMAGE_NAME="$(jq -r --arg l "$LANG" '.images[$l].image // empty' "$LOCK")"
IMAGE_DIGEST="$(jq -r --arg l "$LANG" '.images[$l].digest // empty' "$LOCK")"
EXPECTED_IMAGE="codegolf/lang-${LANG}"
if [ "$IMAGE_NAME" != "$EXPECTED_IMAGE" ] || ! printf '%s\n' "$IMAGE_DIGEST" | grep -Eq '^sha256:[0-9a-f]{64}$'; then
  echo "::error::missing or invalid Docker digest lock for lang=$LANG"
  exit 1
fi
IMAGE="${IMAGE_NAME}@${IMAGE_DIGEST}"

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

# config.initLangs() reads this file in production builds. The digest is only
# used for UI metadata, not for judging, so an empty map is enough for CI.
if [ ! -f /lang-digests.json ]; then
  echo '{}' | sudo tee /lang-digests.json >/dev/null
fi

# Build official run-lang sandbox helper from upstream source.
gcc -Wall -Werror -Wextra -o "$WORKDIR/run-lang" -s -static "$UPSTREAM_ROOT/run-lang.c"
sudo install -m 0755 "$WORKDIR/run-lang" /usr/bin/run-lang
sudo mkdir -p /run_root "/langs/$LANG/rootfs"
sudo rm -rf "/langs/$LANG/rootfs"
sudo mkdir -p "/langs/$LANG/rootfs"

# Materialize exactly the language rootfs that official code.golf uses.
docker pull "$IMAGE" >/dev/null
CID="$(docker create --entrypoint /bin/true "$IMAGE")"
cleanup_cid() { docker rm -f "$CID" >/dev/null 2>&1 || true; }
trap 'cleanup_cid; rm -rf "$WORKDIR"' EXIT
docker export "$CID" | sudo tar -C "/langs/$LANG/rootfs" -xf -
cleanup_cid

# Build and run the thinnest possible wrapper around upstream hole.Play().
# `main` is an overlay branch, so the Go module/source tree comes from the
# separate upstream checkout while the tiny wrapper comes from this overlay.
PLAY_SRC="$UPSTREAM_ROOT/codex_golf_upstream_play.go"
cp "$ROOT/verify/upstream-play.go" "$PLAY_SRC"
cleanup_play() { rm -f "$PLAY_SRC"; }
trap 'cleanup_play; cleanup_cid; rm -rf "$WORKDIR"' EXIT
(
  cd "$UPSTREAM_ROOT"
  GOEXPERIMENT=jsonv2 go build -o "$WORKDIR/upstream-play" "$PLAY_SRC"
)
sudo "$WORKDIR/upstream-play" "$HOLE" "$LANG" "$SOL"
