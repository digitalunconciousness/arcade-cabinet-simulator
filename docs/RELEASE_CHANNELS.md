# Release Channels

This document defines how Arcade Fault Simulator publishes stable and nightly builds.

## Channel model

- **Stable**: production-ready releases intended for all end users.
- **Nightly**: opt-in prerelease builds for testers and development validation.

Nightly uses a separate app identifier (`com.arcade-sim.desktop.nightly`) so
nightly installs can coexist with stable installs on the same machine.

## Workflows

- Stable workflow: `.github/workflows/release.yml`
  - Trigger: tag push matching `v[0-9]*`
  - Release type: normal GitHub release (not prerelease)
  - Config: `src-tauri/tauri.conf.json`

- Nightly workflow: `.github/workflows/nightly.yml`
  - Trigger: daily schedule + manual dispatch
  - Release type: prerelease under fixed tag `nightly`
  - Config: `src-tauri/tauri.nightly.conf.json`
  - Version format: `0.1.0-nightly.<run_number>`

## Updater feeds

- Stable feed endpoint: `.../releases/latest/download/latest.json`
- Nightly feed endpoint: `.../releases/download/nightly/latest.json`

Because stable and nightly use separate identifiers and endpoints, update checks
stay within their own channel and avoid accidental cross-channel upgrades.

## Promotion policy

Use nightly builds for testing and soak-time. Promote to stable only when:

1. Linux and Windows smoke tests pass in CI.
2. First-launch onboarding (ROM path prompt, MAME startup) is validated.
3. No release-blocking regressions remain open.
4. Release notes and migration notes are ready.

## Rollback policy

If a channel release is bad:

1. Re-run the channel workflow from a known-good commit.
2. Verify the release assets and updater JSON were replaced.
3. Announce rollback in release notes/changelog.

For stable, publish a hotfix tag (e.g., `v1.2.4`) rather than mutating an
existing stable tag.
