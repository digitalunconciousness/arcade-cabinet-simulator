#!/usr/bin/env bash
# Mirror the in-repo wiki/ directory to the project's GitHub Wiki repo.
#
# This is a one-way sync. Pages edited in the GitHub Wiki web UI will be
# overwritten on next run. See wiki/Decisions/ADR-0001-wiki-workflow.md.
#
# Usage:
#   tools/sync-wiki.sh                    # uses 'origin' as the source of truth
#   WIKI_REMOTE=upstream tools/sync-wiki.sh
#
# One-time setup (per repo):
#   1. gh repo edit --enable-wiki
#   2. Visit the Wiki tab on github.com/<owner>/<repo> and click
#      "Create the first page" (the wiki repo doesn't exist until then).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/.." && pwd)"
WIKI_SRC="$REPO_ROOT/wiki"
WIKI_REMOTE="${WIKI_REMOTE:-origin}"
if [[ ! -d "$WIKI_SRC" ]]; then
    echo "error: wiki source dir not found at $WIKI_SRC" >&2
    exit 1
fi
# Resolve the wiki repo URL from the named remote.
remote_url="$(cd "$REPO_ROOT" && git remote get-url "$WIKI_REMOTE" 2>/dev/null || true)"
if [[ -z "$remote_url" ]]; then
    echo "error: remote '$WIKI_REMOTE' not configured" >&2
    exit 1
fi
# Map  https://github.com/owner/repo(.git)?  ->  https://github.com/owner/repo.wiki.git
# Map  git@github.com:owner/repo(.git)?       ->  git@github.com:owner/repo.wiki.git
wiki_url="$(printf %s "$remote_url" | sed -E 's#(\.git)?$#.wiki.git#')"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
echo "==> cloning wiki repo: $wiki_url"
if ! git clone --quiet --depth=1 "$wiki_url" "$tmp/wiki"; then
    cat >&2 <<EOF
error: failed to clone wiki repo.
The GitHub wiki must be enabled and have at least one page before the
.wiki.git repo exists. One-time setup:
  gh repo edit --enable-wiki
  # then visit the Wiki tab on github.com/<owner>/<repo> and click
  # "Create the first page".
EOF
    exit 1
fi
echo "==> mirroring $WIKI_SRC -> wiki repo"
# Wipe the wiki working tree (preserving .git) and copy our content over.
find "$tmp/wiki" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
# rsync would be one option; use tar to avoid an extra dep.
( cd "$WIKI_SRC" && tar cf - . ) | ( cd "$tmp/wiki" && tar xf - )
cd "$tmp/wiki"
# GitHub Wikis don't support nested directories in the sidebar, but they
# DO render markdown links and serve files at any depth. Our convention
# uses subdirectories (Phases/, Devices/, Decisions/), which is fine.
if ! git diff --quiet || [[ -n "$(git ls-files --others --exclude-standard)" ]]; then
    git add -A
    git -c user.name="$(git -C "$REPO_ROOT" config user.name)" \
        -c user.email="$(git -C "$REPO_ROOT" config user.email)" \
        commit -m "Sync wiki/ from $(git -C "$REPO_ROOT" rev-parse --short HEAD)" \
        > /dev/null
    echo "==> pushing wiki"
    git push --quiet
    echo "ok"
else
    echo "no changes to sync"
fi
