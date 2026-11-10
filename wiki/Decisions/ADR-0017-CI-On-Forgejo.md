# ADR-0017: Run CI on the owner's Forgejo while GitHub Actions is locked

**Status:** accepted
**Date:** 2026-11-10
**Deciders:** project owner

## Context

GitHub Actions gives this repository no runner: every job since at least 2026-08-10 ends in about 2 seconds with no
logs, including both runs of the new effect-test workflow. The account is locked, and GitHub didn't accept the owner's
card. The owner runs a Forgejo instance on a homelab. Forgejo Actions uses the GitHub Actions workflow format, with
runners the owner hosts.

## Decision

- CI runs on the owner's Forgejo. `.forgejo/workflows/effect-tests.yml` is the Forgejo copy of
  `.github/workflows/effect-tests.yml`, with three differences:
  - the Linux job runs in a `node:22-bookworm` container on a runner labelled `docker`;
  - artifacts upload with Forgejo's build of `upload-artifact`;
  - the Windows job runs on a self-hosted Windows runner (label `windows`, host mode) only when the repository variable
    `CABSIM_WINDOWS` is `true`.
- Both workflows build MAME with one script, `tools/ci/build-mame.sh`, which also works locally.
- `tools/forgejo/sync-github-to-forgejo.sh` copies branches and tags from GitHub to an ordinary Forgejo repository on a
  timer, so every commit reaches Forgejo as a push. A pull mirror isn't used, because Forgejo keeps Actions off for
  mirrors.
- The GitHub workflow stays, so CI comes back there once the account is unlocked.
- Setup steps: `docs/ci-forgejo.md`.

## Consequences

- "CI on windows-latest" (PLAN v0.3) becomes "CI on a Windows 10 or 11 runner the owner hosts". Windows stays unproven
  until one is registered.
- CI results live on the owner's Forgejo. A Claude session sees them only if the instance is reachable and allowed in
  its environment, or if the owner shares the log or artifact.
- Real-game effect tests can run in CI here, using ROMs that stay on the runner host (`CABSIM_ROMPATH`), which GitHub's
  runners could never do.
