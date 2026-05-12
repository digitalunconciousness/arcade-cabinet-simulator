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

use tauri::{AppHandle, Manager};
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
                if let Err(e) = boot(handle).await {
                    eprintln!("[arcade-sim] boot error: {e}");
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
                    // Drop in reverse order: sidecar, MAME, Xvfb.
                    procs.sidecar = None;
                    procs.mame = None;
                    procs.xvfb = None;
                    kill_stale_processes();
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running Tauri application");
}

// ── Boot sequence ─────────────────────────────────────────────────────────────

async fn boot(app: AppHandle) -> Result<(), String> {
    // Best-effort cleanup in case a prior run left children alive.
    kill_stale_processes();

    // 1. Start Xvfb (virtual X11 display).
    let xvfb_display = ":99";
    eprintln!("[arcade-sim] starting Xvfb on {xvfb_display}…");
    let xvfb_child = start_xvfb(&app, xvfb_display).await?;
    app.state::<SidecarState>().0.lock().unwrap().xvfb = Some(xvfb_child);
    tokio::time::sleep(Duration::from_millis(500)).await;

    // 2. Start MAME emulator with cabinet_bus plugin.
    eprintln!("[arcade-sim] starting MAME…");
    let mame_child = start_mame(&app, xvfb_display).await?;
    app.state::<SidecarState>().0.lock().unwrap().mame = Some(mame_child);
    // Give MAME a moment to initialize and open its window.
    tokio::time::sleep(Duration::from_millis(2000)).await;

    // 3. Spawn the Python sidecar (arcade-sim-server) with DISPLAY set.
    // Clear PYTHONHOME and PYTHONPATH so the PyInstaller bootloader uses its
    // own bundled stdlib and is not confused by any active venv on the host.
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
    wait_for_health(&base_url).await?;

    // 6. Background update check — fire-and-forget.
    check_for_update(app.clone());

    // 7. Navigate the WebView to the running app.
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

    // Fall back to source-tree paths when running via `cargo tauri dev`.
    // Try project-root-relative first, then src-tauri-relative (../), then resource_dir value.
    let rom_path = if rom_path.exists() { rom_path }
        else if Path::new("roms").exists() { PathBuf::from("roms") }
        else { PathBuf::from("../roms") };
    let cfg_path = if cfg_path.exists() { cfg_path }
        else if Path::new("cfg").exists() { PathBuf::from("cfg") }
        else { PathBuf::from("../cfg") };
    let plugins_path = if plugins_path.exists() { plugins_path }
        else if Path::new("vendor/mame/plugins").exists() { PathBuf::from("vendor/mame/plugins") }
        else { PathBuf::from("../vendor/mame/plugins") };

    if !rom_path.exists() {
        return Err(format!(
            "ROM path not found at {}; make sure roms/centiped3.zip exists",
            rom_path.display()
        ));
    }

    // Start MAME with cabinet_bus plugin. The plugin listens on port 5051 for
    // TCP commands from the Flask server.
    let mut env = HashMap::new();
    env.insert("DISPLAY".to_string(), display.to_string());
    env.insert("SDL_VIDEODRIVER".to_string(), "x11".to_string());

    eprintln!("[arcade-sim] MAME: binary={mame_bin}, roms={}, cfg={}, plugins={}",
        rom_path.display(), cfg_path.display(), plugins_path.display());

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

    // 4. Search PATH for mame binary.
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

fn kill_stale_processes() {
    // Keep this broad enough to clean up orphaned processes from prior runs.
    let _ = std::process::Command::new("pkill")
        .args(["-f", "arcade-sim-server --tauri-sidecar"])
        .output();
    let _ = std::process::Command::new("pkill")
        .args(["-f", "vendor/mame/mame"])
        .output();
    let _ = std::process::Command::new("pkill")
        .args(["-f", "Xvfb :99"])
        .output();
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

// ── Auto-updater ──────────────────────────────────────────────────────────────

fn check_for_update(app: AppHandle) {
    tauri::async_runtime::spawn(async move {
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

