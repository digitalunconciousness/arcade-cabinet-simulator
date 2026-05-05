// src-tauri/src/lib.rs
//
// Boot sequence for the Arcade Fault Simulator desktop app (Tauri 2.x).
//
// Sequence on startup:
//   1. Window opens showing ui/splash.html.
//   2. Background task spawns the arcade-sim-server sidecar with
//      --tauri-sidecar.
//   3. Reads stdout until "PORT=<n>" appears (10 s timeout).
//   4. Polls GET /api/health on that port until 200 (10 s timeout).
//   5. Checks /api/mame/runtime_info; if mame_found=false, opens a
//      native file-picker so the user can locate their MAME binary and
//      persists the result to ~/.arcade-sim/config.json.
//   6. Navigates the WebView to http://127.0.0.1:<port>.
//
// On last window close the sidecar child is killed (CommandChild Drop sends
// SIGTERM; the OS cleans up if the process doesn't exit in time).

use std::io::{self, BufRead, BufReader, Read, Write};
use std::net::SocketAddr;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use tauri::{AppHandle, Manager};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

/// Shared handle to the running sidecar process.
struct SidecarState(Mutex<Option<CommandChild>>);

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .manage(SidecarState(Mutex::new(None)))
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
                    // Last window — drop the child to send SIGTERM.
                    let state = window.app_handle().state::<SidecarState>();
                    let _child = state.0.lock().unwrap().take();
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running Tauri application");
}

// ── Boot sequence ─────────────────────────────────────────────────────────────

async fn boot(app: AppHandle) -> Result<(), String> {
    // 1. Spawn the Python sidecar.
    // Clear PYTHONHOME and PYTHONPATH so the PyInstaller bootloader uses its
    // own bundled stdlib and is not confused by any active venv on the host.
    let (mut rx, child) = app
        .shell()
        .sidecar("arcade-sim-server")
        .map_err(|e| format!("sidecar lookup failed: {e}"))?
        .args(["--tauri-sidecar"])
        .env("PYTHONHOME", "")
        .env("PYTHONPATH", "")
        .spawn()
        .map_err(|e| format!("sidecar spawn failed: {e}"))?;

    *app.state::<SidecarState>().0.lock().unwrap() = Some(child);

    // 2. Read stdout for PORT=<n> (10 s timeout).
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

    // 3. Poll /api/health until 200 (10 s timeout).
    let base_url = format!("http://127.0.0.1:{port}");
    wait_for_health(&base_url).await?;

    // 4. First-run MAME check — show path picker if mame_found=false.
    first_run_mame_check(&app, &base_url).await;

    // 5. Navigate the WebView to the running app.
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

