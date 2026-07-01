#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use tauri::{Manager, RunEvent, path::BaseDirectory};

struct BackendChild(Mutex<Option<Child>>);

const APP_DATA_FOLDER: &str = "Recipe Tree Visualizer";

fn prepend_to_path(dir: &Path) {
    let has_uv = dir.join("uv.exe").is_file() || dir.join("uv").is_file();
    if !has_uv {
        return;
    }
    let Ok(path) = std::env::var("PATH") else {
        return;
    };
    let dir_str = dir.to_string_lossy();
    if path.split(';').any(|entry| entry.eq_ignore_ascii_case(dir_str.as_ref())) {
        return;
    }
    #[allow(unsafe_code)]
    unsafe {
        std::env::set_var("PATH", format!("{};{}", dir_str, path));
    }
}

fn ensure_uv_in_path() {
    if let Ok(home) = std::env::var("USERPROFILE") {
        prepend_to_path(&Path::new(&home).join(".local").join("bin"));
        prepend_to_path(&Path::new(&home).join(".cargo").join("bin"));
    }
    if let Ok(local) = std::env::var("LOCALAPPDATA") {
        prepend_to_path(&Path::new(&local).join("Programs").join("uv"));
    }
    if let Ok(program_files) = std::env::var("ProgramFiles") {
        prepend_to_path(&Path::new(&program_files).join("uv"));
    }
}

fn app_data_dir() -> PathBuf {
    std::env::var("APPDATA")
        .map(|appdata| PathBuf::from(appdata).join(APP_DATA_FOLDER))
        .unwrap_or_else(|_| PathBuf::from(".").join(APP_DATA_FOLDER))
}

fn ensure_app_data_dirs(data_dir: &Path) {
    let _ = std::fs::create_dir_all(data_dir.join("MinecraftVersions"));
    let _ = std::fs::create_dir_all(data_dir.join("logs"));
}

fn apply_data_env(cmd: &mut Command, data_dir: &Path) {
    ensure_app_data_dirs(data_dir);
    let versions = data_dir.join("MinecraftVersions");
    let logs = data_dir.join("logs");
    cmd.env("RTV_DATA_DIR", data_dir);
    cmd.env("MINECRAFT_VERSIONS_DIR", &versions);
    cmd.env("LOG_DIR", &logs);
    cmd.env("PROJECT_HOST_PATH", data_dir);
}

fn resolve_dev_backend_dir() -> Option<PathBuf> {
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

fn wait_for_backend_port(timeout: Duration) -> bool {
    let deadline = Instant::now() + timeout;
    while Instant::now() < deadline {
        if std::net::TcpStream::connect("127.0.0.1:8000").is_ok() {
            return true;
        }
        std::thread::sleep(Duration::from_millis(200));
    }
    false
}

fn spawn_uvicorn(cmd: &mut Command, backend_cwd: &Path, data_dir: &Path) -> Option<Child> {
    apply_data_env(cmd, data_dir);

    if let Ok(java_home) = std::env::var("RTV_JAVA_HOME") {
        cmd.env("JAVA_HOME", java_home);
    }

    cmd.current_dir(backend_cwd)
        .stdout(Stdio::null())
        .stderr(Stdio::null());

    match cmd.spawn() {
        Ok(child) => Some(child),
        Err(err) => {
            eprintln!("Failed to start backend: {err}");
            None
        }
    }
}

fn start_backend_dev() -> Option<Child> {
    ensure_uv_in_path();
    let backend_dir = resolve_dev_backend_dir()?;
    let data_dir = backend_dir
        .parent()
        .map(|p| p.to_path_buf())
        .unwrap_or_else(app_data_dir);

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

    if let Some(repo_root) = backend_dir.parent() {
        cmd.env("RTV_REPO_ROOT", repo_root);
    }

    spawn_uvicorn(&mut cmd, &backend_dir, &data_dir)
}

fn start_backend_bundled(app: &tauri::AppHandle) -> Option<Child> {
    let resource_root = app
        .path()
        .resolve("backend-bundle", BaseDirectory::Resource)
        .ok()?;
    let python = resource_root.join("python").join("python.exe");
    let backend_cwd = resource_root.join("backend");

    if !python.is_file() || !backend_cwd.join("app").join("main.py").is_file() {
        eprintln!(
            "Bundled backend missing at {}. Run scripts/build-backend-bundle.ps1 before release build.",
            resource_root.display()
        );
        return None;
    }

    let data_dir = app_data_dir();
    let mut cmd = Command::new(&python);
    cmd.args([
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
    ]);

    spawn_uvicorn(&mut cmd, &backend_cwd, &data_dir)
}

fn start_backend(app: &tauri::AppHandle) -> Option<Child> {
    if cfg!(debug_assertions) {
        start_backend_dev()
    } else {
        start_backend_bundled(app).or(start_backend_dev())
    }
}

fn stop_backend(app: &tauri::AppHandle) {
    if let Some(state) = app.try_state::<BackendChild>() {
        if let Ok(mut guard) = state.0.lock() {
            if let Some(mut child) = guard.take() {
                let _ = child.kill();
                let _ = child.wait();
            }
        }
    }
}

fn main() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(BackendChild(Mutex::new(None)))
        .setup(|app| {
            let child = start_backend(app.handle());
            if let Some(state) = app.try_state::<BackendChild>() {
                if let Ok(mut guard) = state.0.lock() {
                    *guard = child;
                }
            }

            if !wait_for_backend_port(Duration::from_secs(30)) {
                eprintln!(
                    "Backend did not start on 127.0.0.1:8000. Data dir: {}",
                    app_data_dir().display()
                );
            }

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application");

    app.run(|app, event| {
        if matches!(event, RunEvent::Exit) {
            stop_backend(app);
        }
    });
}
