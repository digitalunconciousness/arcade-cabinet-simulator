# ADR-0011: Native shell direction (supersedes ADR-0009)

**Status:** accepted
**Date:** 2026-11-09
**Deciders:** project owner (PLAN v0.3)
**Supersedes:** [ADR-0009](ADR-0009-Desktop-Shell-Tauri.md)

## Context

ADR-0009 chose a Tauri WebView over a Python sidecar. As built, the app starts a hidden Xvfb display, MAME and a
PyInstaller Flask server, then shows MAME's output as an MJPEG stream in the WebView. That only runs on Linux, and
it can't become a 3D cabinet. PLAN v0.3 makes Windows a first-class target and moves the UI to a native 3D app.

## Decision

- The app becomes a native Godot 4.7 project that spawns MAME, draws its frames on the monitor mesh and talks to the
  plugin over a versioned JSON-lines protocol (Sim Control Protocol v1). How frames get from MAME to Godot is
  measured in the Stage 2 spike and gets its own ADR.
- Retired: Xvfb, the MJPEG stream, the Flask server, the PyInstaller sidecar and the Tauri WebView.
- The Tauri app stays on `main` until the Stage 2 Godot spike works (the owner's call on 2026-11-09), so there is
  always a runnable UI. The last pre-v0.3 commit is the `legacy-tauri` tag (`d67471b`), which is where the code lives
  for good once it leaves `main`.

## Consequences

- No new work goes into `src-tauri/`, `ui/`, `tools/cabinet_bus/` or the PyInstaller build. Fixes there only if they
  block an audit or a demo.
- The nightly and release workflows keep publishing the Tauri app until it leaves `main`. They clone MAME `master`,
  not the pinned tag (ADR-0010), and build the plugin from `patches/0002`, which lacks most of the commands the UI
  sends (see `docs/FAULT_AUDIT.md`).
