// src-tauri/src/main.rs
// Tauri 2.x entry point.  The application logic lives in lib.rs so it can
// be tested independently of the OS process boundary.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    // Optional compatibility mode for older Linux/AppImage environments.
    // Keep modern compositing defaults unless explicitly requested via
    // ARCADE_SIM_SAFE_WEBKIT=1.
    #[cfg(target_os = "linux")]
    {
        if std::env::var("ARCADE_SIM_SAFE_WEBKIT").ok().as_deref() == Some("1") {
            if std::env::var_os("WEBKIT_DISABLE_COMPOSITING_MODE").is_none() {
                std::env::set_var("WEBKIT_DISABLE_COMPOSITING_MODE", "1");
            }
            if std::env::var_os("LIBGL_ALWAYS_SOFTWARE").is_none() {
                std::env::set_var("LIBGL_ALWAYS_SOFTWARE", "1");
            }
            if std::env::var_os("WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS").is_none() {
                std::env::set_var("WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS", "1");
            }
        }
    }

    arcade_sim_lib::run();
}
