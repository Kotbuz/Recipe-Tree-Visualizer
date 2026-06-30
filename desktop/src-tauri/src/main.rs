#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;

struct BackendChild(Mutex<Option<Child>>);

fn repo_root() -> PathBuf {
    let manifest = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    manifest.parent().and_then(|p| p.parent()).map_or(manifest, |p| p.to_path_buf())
}

fn start_backend() -> Option<Child> {
    let root = repo_root();
    let backend_dir = root.join("backend");

    let mut cmd = if cfg!(windows) {
        let mut c = Command::new("cmd");
        c.args(["/C", "uv run uvicorn app.main:app --host 127.0.0.1 --port 8000"]);
        c
    } else {
        let mut c = Command::new("uv");
        c.args([
            "run",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ]);
        c
    };

    cmd.current_dir(&backend_dir)
        .stdout(Stdio::null())
        .stderr(Stdio::null());

    if let Ok(java_home) = std::env::var("RTV_JAVA_HOME") {
        cmd.env("JAVA_HOME", java_home);
    }

    match cmd.spawn() {
        Ok(child) => Some(child),
        Err(err) => {
            eprintln!("Failed to start backend (install uv + backend deps): {err}");
            None
        }
    }
}

fn main() {
    let backend = BackendChild(Mutex::new(start_backend()));

    let app = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(backend)
        .setup(|app| {
            if cfg!(debug_assertions) {
                return Ok(());
            }
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.eval(
                    "window.location.replace('http://127.0.0.1:8000');",
                );
            }
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application");

    app.run(|_app, _event| {});
}
