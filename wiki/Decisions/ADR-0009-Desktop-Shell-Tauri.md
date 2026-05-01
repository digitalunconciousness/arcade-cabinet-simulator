# ADR-0009 — Desktop shell: Tauri with Python sidecar

**Status:** accepted  
**Date:** 2025  
**Deciders:** project owner

---

## Context

Phase 9 converts the current Flask/browser development setup into a
downloadable desktop application. Three paths were evaluated:

| Option | Shell | Renderer | Bundle size |
|--------|-------|----------|-------------|
| A — Tauri | Rust (< 1 MB) | System WebView | 5–20 MB |
| B — Electron | Node.js | Bundled Chromium | 150–500 MB |
| C — PySide/PyQt | Python | Qt/WebEngine | 40–80 MB + full UI rewrite |

In all three options the Python Flask backend runs locally and the existing
HTML/CSS/JS/WebGL UI is the primary interface.

## Decision

**Option A — Tauri** is chosen.

The Python server runs as a Tauri *sidecar*: a managed child process that
Tauri spawns on startup, extracts the listening port from its stdout, and
kills when the last window closes. The WebView navigates to
`http://127.0.0.1:{port}` once the health check passes.

## Rationale

1. **No UI rewrite.** The existing HTML/CSS/JS UI, including WebGL shaders,
   runs unchanged inside WebKitGTK (Linux), WebView2 (Windows), or WKWebView
   (macOS). Option C required a full rewrite and would have dropped the shader
   system.

2. **Tiny bundles.** Tauri does not bundle a browser engine. An AppImage
   including the Python sidecar executable typically reaches 15–25 MB. This is
   meaningful because the user's arcade ROM set is already large.

3. **Proven sidecar pattern.** Tauri's `[bundle.externalBin]` mechanism and
   `sidecar()` API are designed for exactly this architecture — launching a
   non-Rust backend as a managed subprocess.

4. **CI tooling.** `tauri-action` for GitHub Actions produces Linux, Windows,
   and macOS release artifacts from a single workflow definition.

5. **Rust is only a build-time dependency.** End users do not install Rust; the
   Tauri shell is compiled to a native binary. Python contributors continue
   running `tools/run-demo.sh` for daily development without any Rust
   involvement.

## Consequences

- A minimal Rust `src-tauri/` directory is added to the repository. It
  contains only the Tauri scaffold plus sidecar boot logic; no business logic
  lives in Rust.

- `tools/cabinet_bus/server.py` gains a `--tauri-sidecar` startup flag that
  writes `PORT={n}` to stdout and binds on a random available port.

- A PyInstaller spec file at `build/pyinstaller/server.spec` produces the
  sidecar binary that Tauri bundles.

- WebKit rendering differences from Chrome must be validated manually for
  each new shader. The existing `crt_*.glsl` shaders are confirmed to work
  in WebKitGTK 2.40+ before the Phase 9 milestone is declared done.

- macOS support is conditional on test hardware. The CI job is gated on a PR
  label until hardware becomes available.

## Alternatives considered and rejected

**Electron (Option B):** The 150–500 MB bundle size is unacceptable for a tool
that primarily runs emulation software the user already has. The maintenance
overhead of keeping Chromium up to date without security regressions is also
non-trivial.

**PySide/PyQt (Option C):** The existing browser-based UI already has a
mature layout, a shader pipeline, and MAME video integration. Rewriting it as
Qt widgets would take longer than the rest of Phase 9 combined and would
permanently lose the WebGL shader system.
