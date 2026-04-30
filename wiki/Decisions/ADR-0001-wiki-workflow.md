# ADR-0001 — Track the wiki in-repo, sync to GitHub Wiki on demand
**Status:** Accepted
**Date:** 2026-04-30
**Phase:** 1
## Context
The project is multi-phase, each phase produces both code and design
prose. We want the prose to stay in lockstep with the code that justifies
it. We also want a styled, navigable rendering of the wiki for someone
landing on the GitHub repo for the first time.
GitHub Wiki gives us the styled rendering — sidebar TOC, search, page
history. But it lives in a separate `<repo>.wiki.git` repository, which
means wiki changes can't be in the same commit (or PR) as code changes.
That separation makes it easy for the wiki to drift out of date.
## Considered options
1. **GitHub Wiki only.** Pure, separate, gets the styled rendering for
   free. But every phase commit becomes a two-step dance, and code-only
   PRs that should have updated the wiki frequently won't. Wiki drift is
   approximately guaranteed on a side-project pace.
2. **In-repo `wiki/` only.** Wiki updates land in the same commit as the
   phase deliverables. Renders fine in the GitHub repo browser. No styled
   sidebar; no separate search.
3. **In-repo `wiki/` as the canonical source, sync to GitHub Wiki when
   convenient.** Atomic updates with code, styled rendering when we want
   it, single source of truth.
## Decision
Option 3.
- The canonical wiki lives at `wiki/` in the main repo.
- Every phase commit MUST update the relevant `wiki/Phases/Phase-N-*.md`
  page, `wiki/Home.md`'s "current phase" pointer, and `wiki/Roadmap.md`'s
  status indicator.
- `tools/sync-wiki.sh` mirrors `wiki/` to the GitHub Wiki repo when
  invoked. The script is one-way (this directory → GitHub Wiki). Direct
  edits in the GitHub Wiki UI are explicitly unsupported and will be
  overwritten on next sync.
- The first sync requires a one-time setup: enabling the wiki feature on
  the GitHub repo (`gh repo edit --enable-wiki`) and creating any first
  page via the GitHub web UI so the wiki repo exists.
## Consequences
**Good:**
- Phase commits are atomic (code + wiki).
- Code review of a PR also reviews the wiki update for that change.
- The wiki survives the GitHub Wiki feature being disabled or replaced.
- `git log --follow wiki/<page>.md` works for wiki history.
**Tolerable:**
- We give up GitHub Wiki's in-place editor. That's fine; we already
  prefer editing in our IDE.
- The sync script needs occasional maintenance.
**Bad:**
- The styled rendering only appears after a sync. If we don't sync, only
  the in-repo browser-rendered markdown is visible. We accept this and
  treat the in-repo `wiki/` as the source of truth.
## Implementation
- `wiki/README.md` — convention doc.
- `wiki/Home.md`, `wiki/Roadmap.md`, `wiki/Phases/`, `wiki/Devices/`,
  `wiki/Decisions/` — initial structure.
- `tools/sync-wiki.sh` — one-way sync script.
- This ADR.
