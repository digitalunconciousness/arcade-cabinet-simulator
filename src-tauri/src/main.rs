// src-tauri/src/main.rs
// Tauri 2.x entry point.  The application logic lives in lib.rs so it can
// be tested independently of the OS process boundary.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    arcade_sim_lib::run();
}
