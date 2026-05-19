// src-tauri/src/main.rs
// Tauri 2.x entry point.  The application logic lives in lib.rs so it can
// be tested independently of the OS process boundary.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    // WebKitWebProcess crashes with SIGABRT when GPU compositing is attempted
    // in sandboxed/AppImage launch environments (e.g. GNOME Software / App
    // Center) where GPU/DRI access is restricted.  Disabling compositing mode
    // forces WebKit onto its software rendering path and prevents the abort.
    //
    // LIBGL_ALWAYS_SOFTWARE=1 ensures Mesa's software renderer supplies all
    // GL function pointers for the WebKitWebProcess renderer subprocess;
    // without it the renderer can call through a null GL extension pointer
    // and SIGABRT.  We strip this variable from MAME's environment in lib.rs
    // before spawning so MAME keeps its full hardware-GL performance.
    //
    // These vars must be set before arcade_sim_lib::run() so they are
    // inherited by WebKit subprocesses when the window first opens.
    #[cfg(target_os = "linux")]
    {
        if std::env::var_os("WEBKIT_DISABLE_COMPOSITING_MODE").is_none() {
            std::env::set_var("WEBKIT_DISABLE_COMPOSITING_MODE", "1");
        }
        if std::env::var_os("LIBGL_ALWAYS_SOFTWARE").is_none() {
            std::env::set_var("LIBGL_ALWAYS_SOFTWARE", "1");
        }
        // Some distro/AppImage combinations crash WebKitNetworkProcess with
        // SIGBUS inside the WebKit sandbox. Disable sandboxing as a desktop
        // fallback to keep the app usable in App Center launch environments.
        if std::env::var_os("WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS").is_none() {
            std::env::set_var("WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS", "1");
        }
    }

    arcade_sim_lib::run();
}
