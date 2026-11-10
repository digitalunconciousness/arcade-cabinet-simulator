#!/usr/bin/env bash
# license:CC0-1.0
# Copy every branch and tag from the GitHub repository to a Forgejo
# repository, so each new commit arrives at Forgejo as an ordinary push and
# starts its Actions workflows (a Forgejo pull mirror doesn't run Actions).
# Run it from cron or a systemd timer on the homelab: docs/ci-forgejo.md.
#
#   FORGEJO_URL=ssh://git@forgejo.lan:2222/you/arcade-cabinet-simulator.git \
#       tools/forgejo/sync-github-to-forgejo.sh
#
# Environment:
#   FORGEJO_URL   required: where to push (SSH with a deploy key, or HTTPS with
#                 a token in the credential helper; never put a token in this file)
#   GITHUB_URL    default: the public GitHub repository
#   SYNC_DIR      local bare copy, default ~/.cache/acs-forgejo-sync.git
#   SYNC_PRUNE=1  also delete branches and tags that GitHub no longer has
#
# The Forgejo repository is a copy for CI: push to GitHub, not to it, or the
# next sync overwrites the change.
set -euo pipefail

: "${FORGEJO_URL:?set FORGEJO_URL to the Forgejo repository to push to}"
GITHUB_URL=${GITHUB_URL:-https://github.com/digitalunconciousness/arcade-cabinet-simulator.git}
SYNC_DIR=${SYNC_DIR:-$HOME/.cache/acs-forgejo-sync.git}

# Only one sync at a time (cron can overlap a slow push).
exec 9>"$SYNC_DIR.lock"
if ! flock -n 9; then
	echo "another sync is running" >&2
	exit 0
fi

if [ ! -d "$SYNC_DIR" ]; then
	git init --quiet --bare "$SYNC_DIR"
fi
export GIT_DIR=$SYNC_DIR

# Branches and tags only: GitHub's refs/pull/* stay behind.
git fetch --quiet --prune --force "$GITHUB_URL" \
	'+refs/heads/*:refs/heads/*' '+refs/tags/*:refs/tags/*'

prune=()
if [ "${SYNC_PRUNE:-0}" = 1 ]; then
	prune=(--prune)
fi
# --porcelain prints one line per ref, flag first: " " fast-forward, "+" forced,
# "*" new, "-" deleted, "!" rejected, "=" unchanged. Print only the ones that
# moved or failed, so a quiet run prints nothing (and cron mails nothing).
status=0
out=$(git push --porcelain "${prune[@]}" "$FORGEJO_URL" \
	'+refs/heads/*:refs/heads/*' '+refs/tags/*:refs/tags/*' 2>&1) || status=$?
grep -E $'^[ +*!-]\t' <<<"$out" || true
if [ "$status" -ne 0 ]; then
	echo "$out" >&2
	exit "$status"
fi
