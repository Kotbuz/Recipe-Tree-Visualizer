#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;

struct BackendChild(Mutex<Option<Child>>);

fn resolve_backend_dir() -> Option<PathBuf> {
    if let Ok(root) = std::env::var("RTV_REPO_ROOT") {
        let backend_dir = PathBuf::from(root).join("backend");
        if backend_dir.join("app").join("main.py").is_file() {
            return Some(backend_dir);
        }
    }

    if let Ok(exe) = std::env::current_exe() {
        if let Some(exe_dir) = exe.parent() {
            for candidate in [
                exe_dir.join("backend"),
                exe_dir.join("..").join("backend"),
                exe_dir.join("..").join("..").join("backend"),
            ] {
                if candidate.join("app").join("main.py").is_file() {
                    return candidate.canonicalize().ok().or(Some(candidate));
                }
            }
        }
    }

    let manifest = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let compile_root = manifest.parent().and_then(|p| p.parent())?;
    let backend_dir = compile_root.join("backend");
    if backend_dir.join("app").join("main.py").is_file() {
        return Some(backend_dir);
    }

    None
}

fn start_backend() -> Option<Child> {
    let backend_dir = resolve_backend_dir()?;

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
            if resolve_backend_dir().is_none() {
                eprintln!(
                    "Backend not found. Install uv, set RTV_REPO_ROOT, or run from a full repo checkout."
                );
            }
            let _ = app;
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application");

    app.run(|_app, _event| {});
}
