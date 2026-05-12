// src-tauri/src/lib.rs
//
// Boot sequence for the Arcade Fault Simulator desktop app (Tauri 2.x).
//
// Sequence on startup:
//   1. Window opens showing ui/splash.html.
//   2. Background task orchestrates:
//      - Start Xvfb virtual display (:99)
//      - Start MAME emulator with cabinet_bus plugin
//      - Spawn the arcade-sim-server sidecar with DISPLAY set
//   3. Reads sidecar stdout until "PORT=<n>" appears (10 s timeout).
//   4. Polls GET /api/health on that port until 200 (10 s timeout).
//   5. Navigates the WebView to http://127.0.0.1:<port>.
//
// On last window close all children are killed gracefully (SIGTERM).

use std::io::{self, BufRead, BufReader, Read, Write};
use std::net::SocketAddr;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};
use std::collections::HashMap;

use tauri::{AppHandle, Manager, State};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;
use tauri_plugin_updater::UpdaterExt;

/// Holds all running child processes: Xvfb, MAME, and the Flask sidecar.
struct AppProcesses {
    xvfb: Option<CommandChild>,
    mame: Option<CommandChild>,
    sidecar: Option<CommandChild>,
}

/// Shared handles to running processes.
struct SidecarState(Mutex<AppProcesses>);

/// Persistent socket bridge to the cabinet_bus Lua plugin inside MAME.
struct MameSocketState {
    writer: Option<std::net::TcpStream>,
    reader: Option<BufReader<std::net::TcpStream>>,
}

struct MameSocketBridge(Mutex<MameSocketState>);

impl MameSocketState {
    fn new() -> Self {
        Self { writer: None, reader: None }
    }

    fn close(&mut self) {
        self.writer.take();
        self.reader.take();
    }

    fn ensure_connection(&mut self) -> Result<(), String> {
        if self.writer.is_some() && self.reader.is_some() {
            return Ok(());
        }
        let addr = "127.0.0.1:5051";
        let socket_addr: SocketAddr = addr
            .parse()
            .map_err(|e: std::net::AddrParseError| e.to_string())?;
        let stream = std::net::TcpStream::connect_timeout(&socket_addr, Duration::from_millis(750))
            .map_err(|e| format!("MAME plugin not reachable at {addr}: {e}"))?;
        stream
            .set_read_timeout(Some(Duration::from_millis(750)))
            .map_err(|e| e.to_string())?;
        stream
            .set_write_timeout(Some(Duration::from_millis(750)))
            .map_err(|e| e.to_string())?;
        let reader = stream
            .try_clone()
            .map(BufReader::new)
            .map_err(|e| e.to_string())?;
        self.reader = Some(reader);
        self.writer = Some(stream);
        Ok(())
    }

    fn send_json(&mut self, cmd: &serde_json::Value) -> Result<serde_json::Value, String> {
        for attempt in 1..=2 {
            match self.send_json_once(cmd) {
                Ok(reply) => return Ok(reply),
                Err(err) if attempt == 1 => {
                    self.close();
                    boot_log(&format!("retrying MAME socket command after error: {err}"));
                }
                Err(err) => return Err(err),
            }
        }
        Err("unexpected MAME socket retry failure".to_string())
    }

    fn send_json_once(&mut self, cmd: &serde_json::Value) -> Result<serde_json::Value, String> {
        self.ensure_connection()?;
        let payload = serde_json::to_string(cmd).map_err(|e| e.to_string())? + "\n";
        {
            let writer = self.writer.as_mut().ok_or_else(|| "missing MAME socket writer".to_string())?;
            writer.write_all(payload.as_bytes()).map_err(|e| e.to_string())?;
        }

        let mut response_line = String::new();
        let bytes_read = {
            let reader = self.reader.as_mut().ok_or_else(|| "missing MAME socket reader".to_string())?;
            reader.read_line(&mut response_line).map_err(|e| e.to_string())?
        };
        if bytes_read == 0 {
            self.close();
            return Err("MAME closed the plugin socket".to_string());
        }

        let reply: serde_json::Value = serde_json::from_str(response_line.trim()).map_err(|e| e.to_string())?;
        if reply.get("ok").and_then(|v| v.as_bool()) == Some(false) {
            let err = reply
                .get("error")
                .and_then(|v| v.as_str())
                .unwrap_or("MAME command failed")
                .to_string();
            return Err(err);
        }
        Ok(reply)
    }
}

fn send_mame_command(bridge: &State<'_, MameSocketBridge>, cmd: serde_json::Value) -> Result<(), String> {
    let mut state = bridge.0.lock().map_err(|_| "MAME bridge lock poisoned".to_string())?;
    state.send_json(&cmd).map(|_| ())
}

#[tauri::command]
fn mame_press_button(bridge: State<'_, MameSocketBridge>, name: String) -> Result<(), String> {
    send_mame_command(&bridge, serde_json::json!({"cmd": "press_button", "name": name}))
}

#[tauri::command]
fn mame_release_button(bridge: State<'_, MameSocketBridge>, name: String) -> Result<(), String> {
    send_mame_command(&bridge, serde_json::json!({"cmd": "release_button", "name": name}))
}

#[tauri::command]
fn mame_trackball_delta(bridge: State<'_, MameSocketBridge>, dx: i32, dy: i32) -> Result<(), String> {
    if dx == 0 && dy == 0 {
        return Ok(());
    }
    send_mame_command(&bridge, serde_json::json!({"cmd": "trackball_delta", "dx": dx, "dy": dy}))
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .manage(SidecarState(Mutex::new(AppProcesses {
            xvfb: None,
            mame: None,
            sidecar: None,
        })))
        .manage(MameSocketBridge(Mutex::new(MameSocketState::new())))
        .invoke_handler(tauri::generate_handler![
            mame_press_button,
            mame_release_button,
            mame_trackball_delta,
        ])
        .setup(|app| {
            // In release builds, navigate to the splash screen immediately
            // so the window shows something while the sidecar starts.
            // In dev mode, about:blank stays until the sidecar port is ready.
            #[cfg(not(debug_assertions))]
            {
                if let Some(w) = app.get_webview_window("main") {
                    let _ = w.navigate("tauri://localhost/splash.html".parse().unwrap());
                }
            }
            let handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                if let Err(e) = boot(handle.clone()).await {
                    eprintln!("[arcade-sim] boot error: {e}");
                    set_splash_error(&handle, &e);
                }
            });
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                if window.app_handle().webview_windows().len() == 1 {
                    // Last window — force-kill known children so relaunch is clean.
                    let state = window.app_handle().state::<SidecarState>();
                    let mut procs = state.0.lock().unwrap();
                    // Kill in reverse order: sidecar, MAME, Xvfb.
                    if let Some(child) = procs.sidecar.take() {
                        let _ = child.kill();
                    }
                    if let Some(child) = procs.mame.take() {
                        let _ = child.kill();
                    }
                    if let Some(child) = procs.xvfb.take() {
                        let _ = child.kill();
                    }
                    kill_stale_processes();
                    window.app_handle().exit(0);
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running Tauri application");
}

// ── Boot sequence ─────────────────────────────────────────────────────────────

async fn boot(app: AppHandle) -> Result<(), String> {
    // Rotate log: truncate on each fresh boot so we don't accumulate stale entries.
    let _ = std::fs::write("/tmp/arcade-sim-boot.log", "");
    let channel = app_release_channel();
    boot_log(&format!("boot start — exe={}", std::env::current_exe().map(|p| p.display().to_string()).unwrap_or_else(|_| "?".into())));
    boot_log(&format!("release_channel={channel}"));
    boot_log(&format!("cwd={}", std::env::current_dir().map(|p| p.display().to_string()).unwrap_or_else(|_| "?".into())));
    boot_log(&format!("HOME={}", std::env::var("HOME").unwrap_or_else(|_| "(unset)".into())));
    boot_log(&format!("DISPLAY={}", std::env::var("DISPLAY").unwrap_or_else(|_| "(unset)".into())));
    boot_log(&format!("PATH={}", std::env::var("PATH").unwrap_or_else(|_| "(unset)".into())));
    // Best-effort cleanup in case a prior run left children alive.
    set_splash_status(&app, 5, "Cleaning stale processes");
    kill_stale_processes();

    // 1. Start Xvfb (virtual X11 display).
    let xvfb_display = ":99";
    set_splash_status(&app, 15, "Starting virtual display (Xvfb)");
    eprintln!("[arcade-sim] starting Xvfb on {xvfb_display}…");
    let xvfb_child = start_xvfb(&app, xvfb_display).await?;
    app.state::<SidecarState>().0.lock().unwrap().xvfb = Some(xvfb_child);
    set_splash_status(&app, 35, "Display ready");
    tokio::time::sleep(Duration::from_millis(500)).await;

    // 2. Start MAME emulator with cabinet_bus plugin.
    set_splash_status(&app, 45, "Launching MAME");
    boot_log("starting MAME…");
    let mame_child = start_mame(&app, xvfb_display).await?;
    app.state::<SidecarState>().0.lock().unwrap().mame = Some(mame_child);
    // Give MAME a moment to initialize and open its window.
    set_splash_status(&app, 60, "MAME booting and loading ROM");
    tokio::time::sleep(Duration::from_millis(2000)).await;
    // Verify MAME is still running — if it crashed early (bad ROM path, missing
    // plugin, etc.) we want to report that now rather than hanging on the sidecar.
    let mame_still_alive = std::process::Command::new("pgrep")
        .args(["-f", "vendor/mame/mame"])
        .output()
        .map(|o| o.status.success())
        .unwrap_or(false);
    if !mame_still_alive {
        boot_log("MAME exited unexpectedly — check paths and ROM");
        return Err(
            "MAME exited immediately. Check that roms/centiped3.zip exists and \
             vendor/mame/plugins/cabinet_bus is present.".to_string()
        );
    }
    boot_log("MAME still running — OK");

    // 3. Spawn the Python sidecar (arcade-sim-server) with DISPLAY set.
    // Clear PYTHONHOME and PYTHONPATH so the PyInstaller bootloader uses its
    // own bundled stdlib and is not confused by any active venv on the host.
    set_splash_status(&app, 70, "Starting API sidecar");
    eprintln!("[arcade-sim] starting arcade-sim-server sidecar…");
    let mut env = HashMap::new();
    env.insert("PYTHONHOME".to_string(), "".to_string());
    env.insert("PYTHONPATH".to_string(), "".to_string());
    env.insert("DISPLAY".to_string(), xvfb_display.to_string());
    env.insert("MAME_DISPLAY".to_string(), xvfb_display.to_string());
    env.insert("SDL_VIDEODRIVER".to_string(), "x11".to_string());

    let (mut rx, child) = app
        .shell()
        .sidecar("arcade-sim-server")
        .map_err(|e| format!("sidecar lookup failed: {e}"))?
        .args(["--tauri-sidecar"])
        .envs(env)
        .spawn()
        .map_err(|e| format!("sidecar spawn failed: {e}"))?;

    app.state::<SidecarState>().0.lock().unwrap().sidecar = Some(child);

    // 4. Read stdout for PORT=<n> (10 s timeout).
    set_splash_status(&app, 80, "Waiting for sidecar port");
    let port = tokio::time::timeout(Duration::from_secs(10), async {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(bytes) => {
                    let line = String::from_utf8_lossy(&bytes);
                    if let Some(rest) = line.trim().strip_prefix("PORT=") {
                        if let Ok(n) = rest.parse::<u16>() {
                            return Some(n);
                        }
                    }
                }
                CommandEvent::Stderr(bytes) => {
                    let _ = io::stderr().write_all(&bytes);
                }
                CommandEvent::Terminated(status) => {
                    eprintln!(
                        "[arcade-sim] sidecar exited early with code {:?}",
                        status.code
                    );
                    return None;
                }
                _ => {}
            }
        }
        None
    })
    .await
    .ok()
    .flatten()
    .ok_or_else(|| "timed out waiting for sidecar PORT".to_string())?;

    // 5. Poll /api/health until 200 (10 s timeout).
    let base_url = format!("http://127.0.0.1:{port}");
    set_splash_status(&app, 90, "Checking API health");
    wait_for_health(&base_url).await?;

    // 6. Background update check — fire-and-forget.
    check_for_update(app.clone());

    // 7. Navigate the WebView to the running app.
    set_splash_status(&app, 100, "Launching interface");
    let window = app
        .get_webview_window("main")
        .ok_or_else(|| "main window not found".to_string())?;
    let url: tauri::Url = base_url
        .parse()
        .map_err(|e| format!("bad sidecar URL: {e}"))?;
    window
        .navigate(url)
        .map_err(|e| format!("navigate failed: {e}"))?;

    Ok(())
}

// ── Xvfb startup ───────────────────────────────────────────────────────────────

async fn start_xvfb(app: &AppHandle, display: &str) -> Result<CommandChild, String> {
    // Start a virtual X11 display so MAME doesn't need a physical monitor.
    // Kill any existing Xvfb on this display to avoid port conflicts.
    let _ = std::process::Command::new("pkill")
        .args(["-f", &format!("Xvfb {}", display)])
        .output();
    
    tokio::time::sleep(Duration::from_millis(200)).await;

    let (_rx, child) = app.shell()
        .command("Xvfb")
        .args([
            display,
            "-screen", "0", "480x640x24",
            "-ac",
        ])
        .spawn()
        .map_err(|e| format!("Xvfb spawn failed: {e}"))?;

    // Ensure the display is actually ready before launching MAME.
    wait_for_display_ready(display)?;
    
    Ok(child)
}

// ── MAME startup ───────────────────────────────────────────────────────────────

async fn start_mame(app: &AppHandle, display: &str) -> Result<CommandChild, String> {
    // Determine paths relative to app (works in both dev and production).
    let app_resource_path = app.path().resource_dir()
        .ok()
        .unwrap_or_else(|| PathBuf::from("."));

    // Find MAME binary: check config, PATH, bundled resource, then relative.
    let mame_bin = find_mame_binary(&app_resource_path)?;

    let rom_path = app_resource_path.join("roms");
    let cfg_path = app_resource_path.join("cfg");
    let plugins_path = app_resource_path.join("vendor/mame/plugins");
    let project_root = find_project_root();

    // Fall back to source-tree paths when running via `cargo tauri dev`.
    // Try resource_dir first, then absolute project-root fallback, then relative paths.
    let rom_path = find_rom_path(&app_resource_path, project_root.as_ref())?;
    let cfg_path = if cfg_path.exists() { cfg_path }
        else if let Some(root) = &project_root { root.join("cfg") }
        else if Path::new("cfg").exists() { PathBuf::from("cfg") }
        else { PathBuf::from("../cfg") };
    let plugins_path = if plugins_path.exists() { plugins_path }
        else if let Some(root) = &project_root { root.join("vendor/mame/plugins") }
        else if Path::new("vendor/mame/plugins").exists() { PathBuf::from("vendor/mame/plugins") }
        else { PathBuf::from("../vendor/mame/plugins") };

    // Start MAME with cabinet_bus plugin. The plugin listens on port 5051 for
    // TCP commands from the Flask server.
    let mut env = HashMap::new();
    env.insert("DISPLAY".to_string(), display.to_string());
    env.insert("SDL_VIDEODRIVER".to_string(), "x11".to_string());

    boot_log(&format!("MAME binary={mame_bin}"));
    boot_log(&format!("  rom_path={} exists={}", rom_path.display(), rom_path.exists()));
    boot_log(&format!("  cfg_path={} exists={}", cfg_path.display(), cfg_path.exists()));
    boot_log(&format!("  plugins_path={} exists={}", plugins_path.display(), plugins_path.exists()));

    let (_rx, child) = app.shell()
        .command(&mame_bin)
        .args([
            "-window",
            "-skip_gameinfo",
            "-inipath", cfg_path.to_str().unwrap_or("cfg"),
            "-rompath", rom_path.to_str().unwrap_or("roms"),
            "-pluginspath", plugins_path.to_str().unwrap_or("vendor/mame/plugins"),
            "-plugin", "cabinet_bus",
            "centiped3",
        ])
        .envs(&env)
        .spawn()
        .map_err(|e| format!("MAME spawn failed: {e}"))?;
    
    Ok(child)
}

fn find_mame_binary(resource_dir: &Path) -> Result<String, String> {
    // 1. Check config file for saved MAME path.
    if let Some(home) = std::env::var_os("HOME").map(PathBuf::from) {
        let config_file = home.join(".arcade-sim/config.json");
        if let Ok(content) = std::fs::read_to_string(&config_file) {
            if let Ok(json) = serde_json::from_str::<serde_json::Value>(&content) {
                if let Some(path) = json.get("mame_binary").and_then(|v| v.as_str()) {
                    let p = Path::new(path);
                    if p.is_file() && is_executable(p) {
                        return Ok(path.to_string());
                    }
                }
            }
        }
    }

    // 2. Bundled resource (production AppImage): resource_dir/vendor/mame/mame
    let bundled = resource_dir.join("vendor/mame/mame");
    if bundled.is_file() && is_executable(&bundled) {
        return Ok(bundled.to_string_lossy().into_owned());
    }

    // 3. Source-tree relative paths (cargo tauri dev).
    for dev_path in &["vendor/mame/mame", "../vendor/mame/mame"] {
        let p = Path::new(dev_path);
        if p.is_file() && is_executable(p) {
            return Ok(p.to_string_lossy().into_owned());
        }
    }

    // 4. Absolute project-root fallback (stable when launched from App Center).
    if let Some(root) = find_project_root() {
        let p = root.join("vendor/mame/mame");
        if p.is_file() && is_executable(&p) {
            return Ok(p.to_string_lossy().into_owned());
        }
    }

    // 5. Search PATH for mame binary.
    if let Ok(path_env) = std::env::var("PATH") {
        for dir in path_env.split(':') {
            let candidate = Path::new(dir).join("mame");
            if candidate.is_file() && is_executable(&candidate) {
                return Ok(candidate.to_string_lossy().into_owned());
            }
        }
    }

    Err(
        "MAME binary not found. Build vendor/mame/mame or set mame_binary in ~/.arcade-sim/config.json".to_string()
    )
}

fn find_rom_path(resource_dir: &Path, project_root: Option<&PathBuf>) -> Result<PathBuf, String> {
    // 1. Explicit env override.
    if let Ok(path) = std::env::var("ARCADE_SIM_ROM_PATH") {
        let p = PathBuf::from(path);
        return validate_rom_path(&p);
    }

    // 2. Config file override.
    if let Some(home) = std::env::var_os("HOME").map(PathBuf::from) {
        let config_file = home.join(".arcade-sim/config.json");
        if let Ok(content) = std::fs::read_to_string(&config_file) {
            if let Ok(json) = serde_json::from_str::<serde_json::Value>(&content) {
                if let Some(path) = json.get("rom_path").and_then(|v| v.as_str()) {
                    let p = PathBuf::from(path);
                    return validate_rom_path(&p);
                }
            }
        }
    }

    // 3. Bundled and dev fallbacks.
    let candidates = [
        resource_dir.join("roms"),
        project_root.map(|p| p.join("roms")).unwrap_or_default(),
        PathBuf::from("roms"),
        PathBuf::from("../roms"),
    ];

    for candidate in candidates {
        if candidate.as_os_str().is_empty() {
            continue;
        }
        if let Ok(path) = validate_rom_path(&candidate) {
            return Ok(path);
        }
    }

    Err(
        "ROM directory not found or missing centiped3.zip. Set ARCADE_SIM_ROM_PATH or \
         configure rom_path in ~/.arcade-sim/config.json"
            .to_string(),
    )
}

fn validate_rom_path(path: &Path) -> Result<PathBuf, String> {
    if !path.exists() {
        return Err(format!("ROM path does not exist: {}", path.display()));
    }
    if !path.is_dir() {
        return Err(format!("ROM path is not a directory: {}", path.display()));
    }

    let required = path.join("centiped3.zip");
    if !required.exists() {
        return Err(format!(
            "ROM directory {} is missing centiped3.zip",
            path.display()
        ));
    }
    Ok(path.to_path_buf())
}

fn find_project_root() -> Option<PathBuf> {
    let mut candidates: Vec<PathBuf> = Vec::new();

    if let Ok(cwd) = std::env::current_dir() {
        candidates.push(cwd);
    }
    if let Ok(exe) = std::env::current_exe() {
        if let Some(parent) = exe.parent() {
            candidates.push(parent.to_path_buf());
            if let Some(grand) = parent.parent() {
                candidates.push(grand.to_path_buf());
            }
        }
    }
    if let Some(home) = std::env::var_os("HOME").map(PathBuf::from) {
        candidates.push(home.join("arcade-sim"));
    }

    for base in candidates {
        // Check both base and one level up.
        for root in [base.clone(), base.join("..")]
            .iter()
            .filter_map(|p| p.canonicalize().ok())
        {
            if root.join("roms").exists()
                && root.join("cfg").exists()
                && root.join("vendor/mame/plugins").exists()
            {
                return Some(root);
            }
        }
    }
    None
}

fn is_executable(path: &Path) -> bool {
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        if let Ok(metadata) = std::fs::metadata(path) {
            let permissions = metadata.permissions();
            permissions.mode() & 0o111 != 0
        } else {
            false
        }
    }
    #[cfg(not(unix))]
    {
        path.is_file()
    }
}

fn wait_for_display_ready(display: &str) -> Result<(), String> {
    let deadline = Instant::now() + Duration::from_secs(5);
    loop {
        let ok = std::process::Command::new("xdpyinfo")
            .args(["-display", display])
            .output()
            .map(|o| o.status.success())
            .unwrap_or(false);
        if ok {
            return Ok(());
        }
        if Instant::now() >= deadline {
            return Err(format!("Xvfb display {display} did not become ready within 5 s"));
        }
        std::thread::sleep(Duration::from_millis(100));
    }
}

fn kill_stale_processes() {
    // Keep this broad enough to clean up orphaned processes from prior runs.
    let _ = std::process::Command::new("pkill")
        .args(["-f", "arcade-sim-server --tauri-sidecar"])
        .output();
    let _ = std::process::Command::new("pkill")
        .args(["-f", "mame .* -plugin cabinet_bus"])
        .output();
    let _ = std::process::Command::new("pkill")
        .args(["-f", "vendor/mame/mame"])
        .output();
    let _ = std::process::Command::new("pkill")
        .args(["-f", "Xvfb :99"])
        .output();
}

/// Append a timestamped line to /tmp/arcade-sim-boot.log AND stderr.
fn boot_log(msg: &str) {
    use std::io::Write as _;
    let ts = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    eprintln!("[arcade-sim] {msg}");
    if let Ok(mut f) = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open("/tmp/arcade-sim-boot.log")
    {
        let _ = f.write_all(format!("[{ts}] {msg}\n").as_bytes());
    }
}

fn set_splash_status(app: &AppHandle, percent: u8, message: &str) {
    if let Some(window) = app.get_webview_window("main") {
        let msg = serde_json::to_string(message).unwrap_or_else(|_| "\"Starting...\"".to_string());
        let script = format!(
            "if (window.__bootProgress) {{ window.__bootProgress({}, {}); }}",
            percent.min(100),
            msg
        );
        let _ = window.eval(&script);
    }
}

fn set_splash_error(app: &AppHandle, message: &str) {
    if let Some(window) = app.get_webview_window("main") {
        let msg = serde_json::to_string(message).unwrap_or_else(|_| "\"Boot failed\"".to_string());
        let script = format!(
            "if (window.__bootError) {{ window.__bootError({}); }}",
            msg
        );
        let _ = window.eval(&script);
    }
}

// ── HTTP helpers — std::net (blocking, loopback only) ─────────────────────────

/// Parse `http://host:port/path` into `(host, port, path)`.
fn parse_http_url(url: &str) -> Option<(String, u16, String)> {
    let rest = url.strip_prefix("http://")?;
    let (authority, tail) = rest.split_once('/').unwrap_or((rest, ""));
    let path = format!("/{tail}");
    let (host, port) = if let Some((h, p)) = authority.split_once(':') {
        (h.to_string(), p.parse::<u16>().ok()?)
    } else {
        (authority.to_string(), 80_u16)
    };
    Some((host, port, path))
}

/// Blocking GET; returns the HTTP status code (0 on connection error).
fn http_get_status(url: &str) -> u16 {
    let Some((host, port, path)) = parse_http_url(url) else {
        return 0;
    };
    let Ok(addr) = format!("{host}:{port}").parse::<SocketAddr>() else {
        return 0;
    };
    let Ok(stream) = std::net::TcpStream::connect_timeout(&addr, Duration::from_secs(1)) else {
        return 0;
    };
    let _ = stream.set_read_timeout(Some(Duration::from_secs(2)));
    let req = format!("GET {path} HTTP/1.0\r\nHost: {host}\r\nConnection: close\r\n\r\n");
    if (&stream).write_all(req.as_bytes()).is_err() {
        return 0;
    }
    let mut buf = [0u8; 12];
    if (&stream).read_exact(&mut buf).is_err() {
        return 0;
    }
    // "HTTP/1.x 200 OK…" — status code at bytes 9..12.
    std::str::from_utf8(&buf[9..12])
        .ok()
        .and_then(|s| s.parse().ok())
        .unwrap_or(0)
}

/// Blocking GET; returns parsed JSON body or an error.
fn http_get_json(url: &str) -> io::Result<serde_json::Value> {
    let (host, port, path) = parse_http_url(url)
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, "bad url"))?;
    let addr: SocketAddr = format!("{host}:{port}")
        .parse()
        .map_err(|e: std::net::AddrParseError| io::Error::new(io::ErrorKind::InvalidInput, e))?;
    let stream = std::net::TcpStream::connect_timeout(&addr, Duration::from_secs(3))?;
    stream.set_read_timeout(Some(Duration::from_secs(3)))?;
    let req = format!("GET {path} HTTP/1.0\r\nHost: {host}\r\nConnection: close\r\n\r\n");
    (&stream).write_all(req.as_bytes())?;
    // Skip response headers.
    let mut reader = BufReader::new(&stream);
    let mut line = String::new();
    loop {
        line.clear();
        reader.read_line(&mut line)?;
        if line.trim().is_empty() {
            break;
        }
    }
    // Read JSON body.
    let mut body = String::new();
    reader.read_to_string(&mut body)?;
    serde_json::from_str(&body).map_err(|e| io::Error::new(io::ErrorKind::InvalidData, e))
}

// ── Health poll ───────────────────────────────────────────────────────────────

async fn wait_for_health(base_url: &str) -> Result<(), String> {
    let health_url = format!("{base_url}/api/health");
    let deadline = Instant::now() + Duration::from_secs(10);
    loop {
        let url = health_url.clone();
        if let Ok(200) = tokio::task::spawn_blocking(move || http_get_status(&url)).await {
            return Ok(());
        }
        if Instant::now() >= deadline {
            return Err(format!(
                "sidecar at {base_url} did not become healthy within 10 s"
            ));
        }
        tokio::time::sleep(Duration::from_millis(200)).await;
    }
}

// ── First-run MAME path picker ────────────────────────────────────────────────

async fn first_run_mame_check(app: &AppHandle, base_url: &str) {
    let url = format!("{base_url}/api/mame/runtime_info");
    if let Ok(Ok(json)) = tokio::task::spawn_blocking(move || http_get_json(&url)).await {
        let mame_found = json
            .as_object()
            .and_then(|o| o.get("mame_found"))
            .and_then(|v| v.as_bool())
            .unwrap_or(true);
        if !mame_found {
            show_mame_picker(app).await;
        }
    }
}

async fn show_mame_picker(app: &AppHandle) {
    use tauri_plugin_dialog::DialogExt;

    let (tx, rx) = tokio::sync::oneshot::channel::<Option<PathBuf>>();
    let tx = Arc::new(Mutex::new(Some(tx)));

    app.dialog()
        .file()
        .set_title("Locate your MAME binary")
        .pick_file(move |path| {
            let resolved = path.and_then(|p| p.into_path().ok());
            let _ = tx.lock().unwrap().take().map(|s| s.send(resolved));
        });

    if let Ok(Some(path)) = rx.await {
        if let Err(e) = save_mame_binary(&path) {
            eprintln!("[arcade-sim] could not save MAME path: {e}");
        } else {
            eprintln!("[arcade-sim] MAME binary set to {}", path.display());
        }
    }
}

fn save_mame_binary(path: &Path) -> io::Result<()> {
    let config_dir = std::env::var_os("HOME")
        .map(PathBuf::from)
        .ok_or_else(|| io::Error::new(io::ErrorKind::NotFound, "HOME not set"))?
        .join(".arcade-sim");
    std::fs::create_dir_all(&config_dir)?;
    let config_file = config_dir.join("config.json");
    let mut config: serde_json::Value = if config_file.exists() {
        serde_json::from_str(&std::fs::read_to_string(&config_file).unwrap_or_default())
            .unwrap_or_else(|_| serde_json::json!({}))
    } else {
        serde_json::json!({})
    };
    config["mame_binary"] = serde_json::Value::String(path.to_string_lossy().into_owned());
    std::fs::write(config_file, serde_json::to_string_pretty(&config)? + "\n")
}

fn app_release_channel() -> String {
    std::env::var("ARCADE_SIM_CHANNEL")
        .ok()
        .map(|s| s.trim().to_lowercase())
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| "stable".to_string())
}

// ── Auto-updater ──────────────────────────────────────────────────────────────

fn check_for_update(app: AppHandle) {
    tauri::async_runtime::spawn(async move {
        let channel = app_release_channel();
        eprintln!("[arcade-sim] updater channel={channel}");
        let updater = match app.updater() {
            Ok(u) => u,
            Err(e) => {
                eprintln!("[arcade-sim] updater init: {e}");
                return;
            }
        };
        match updater.check().await {
            Ok(Some(update)) => {
                eprintln!(
                    "[arcade-sim] update v{} available — downloading…",
                    update.version
                );
                if let Err(e) = update
                    .download_and_install(|_downloaded, _total| {}, || {})
                    .await
                {
                    eprintln!("[arcade-sim] update install failed: {e}");
                }
            }
            Ok(None) => {}
            Err(e) => eprintln!("[arcade-sim] update check: {e}"),
        }
    });
}

