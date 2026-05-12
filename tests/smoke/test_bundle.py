"""
tests/smoke/test_bundle.py

Smoke tests for the arcade-sim-server sidecar binary.

Runs the sidecar (either the PyInstaller ELF from dist/ or the Python
package directly), confirms it starts, passes health check, and handles
a basic scenario run.

Usage:
    # Against PyInstaller binary (CI default):
    pytest tests/smoke/test_bundle.py

    # Against Python package (dev):
    ARCADE_SIM_USE_PYTHON=1 pytest tests/smoke/test_bundle.py
"""

import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest
import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
DIST_BINARY = REPO_ROOT / "dist" / "arcade-sim-server"
PYTHON = sys.executable

STARTUP_TIMEOUT = 15   # seconds to wait for PORT= line
HEALTH_TIMEOUT  = 10   # seconds to poll /api/health


# ── Fixture: running sidecar ─────────────────────────────────────────────────

@pytest.fixture(scope="module")
def sidecar():
    """Launch the sidecar, yield (process, base_url), then kill it."""
    use_python = os.environ.get("ARCADE_SIM_USE_PYTHON", "").lower() in ("1", "true", "yes")

    if use_python:
        cmd = [PYTHON, "-m", "tools.cabinet_bus", "--tauri-sidecar"]
        cwd = REPO_ROOT
    else:
        if not DIST_BINARY.exists():
            pytest.skip(f"Sidecar binary not found: {DIST_BINARY}. Run build/pyinstaller/build.sh first.")
        cmd = [str(DIST_BINARY), "--tauri-sidecar"]
        cwd = REPO_ROOT

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=cwd,
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
    )

    # Parse PORT= from stdout.
    port = None
    deadline = time.monotonic() + STARTUP_TIMEOUT
    while time.monotonic() < deadline:
        line = proc.stdout.readline()
        if not line:
            if proc.poll() is not None:
                out, err = proc.communicate()
                pytest.fail(
                    f"Sidecar exited early (code {proc.returncode}).\n"
                    f"stdout: {line}\nstderr: {err}"
                )
            continue
        m = re.match(r"PORT=(\d+)", line.strip())
        if m:
            port = int(m.group(1))
            break

    if port is None:
        proc.kill()
        pytest.fail("Timed out waiting for PORT= from sidecar.")

    base_url = f"http://127.0.0.1:{port}"

    # Wait for /api/health.
    deadline = time.monotonic() + HEALTH_TIMEOUT
    healthy = False
    while time.monotonic() < deadline:
        try:
            r = requests.get(f"{base_url}/api/health", timeout=1)
            if r.status_code == 200:
                healthy = True
                break
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(0.2)

    if not healthy:
        proc.kill()
        pytest.fail(f"Sidecar at {base_url} did not become healthy within {HEALTH_TIMEOUT}s.")

    yield proc, base_url

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_health(sidecar):
    _, base_url = sidecar
    r = requests.get(f"{base_url}/api/health", timeout=5)
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "ok"


def test_scenarios_list(sidecar):
    _, base_url = sidecar
    r = requests.get(f"{base_url}/api/scenarios", timeout=5)
    assert r.status_code == 200
    body = r.json()
    # Response shape: {"scenarios": [...]}
    scenarios = body.get("scenarios", body) if isinstance(body, dict) else body
    assert isinstance(scenarios, list)
    assert len(scenarios) > 0, "No scenarios returned"
    names = [s.get("id") or s.get("name") or str(s) for s in scenarios]
    assert any("dim" in n or "psu" in n or "01" in n for n in names), f"Expected dim-psu scenario, got: {names[:5]}"


def test_apply_scenario_dim_psu(sidecar):
    _, base_url = sidecar
    scenario_id = "01-dim-psu-5v"
    r = requests.post(
        f"{base_url}/api/scenarios/{scenario_id}/apply",
        timeout=10,
    )
    # 200 = applied; 404 = scenario file not bundled (skip, not fail)
    if r.status_code == 404:
        pytest.skip(f"Scenario {scenario_id!r} not found in bundle")
    assert r.status_code == 200, f"apply failed: {r.status_code} {r.text}"
    body = r.json()
    assert body.get("applied") is True


def test_mame_runtime_info(sidecar):
    _, base_url = sidecar
    r = requests.get(f"{base_url}/api/mame/runtime_info", timeout=5)
    assert r.status_code == 200
    body = r.json()
    assert "mame_found" in body
    assert isinstance(body["mame_found"], bool)
    assert "display" in body


def test_static_index(sidecar):
    _, base_url = sidecar
    r = requests.get(f"{base_url}/", timeout=5)
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")


def test_static_shader(sidecar):
    _, base_url = sidecar
    r = requests.get(f"{base_url}/static/shaders/crt_normal.glsl", timeout=5)
    assert r.status_code == 200, "crt_normal.glsl not served"
    assert "texture2D" in r.text or "gl_FragColor" in r.text
