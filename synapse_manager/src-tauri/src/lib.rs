mod terminal;
mod udp;

use serde::{Deserialize, Serialize};
use std::{
    collections::HashMap,
    fs,
    path::{Path, PathBuf},
    process::Command,
};
use tauri::{AppHandle, Manager};
use tauri_plugin_dialog::DialogExt;
use tauri_plugin_opener::OpenerExt;
use terminal::open_ssh_terminal;

#[derive(Debug, Serialize, Deserialize, Default)]
struct AppConfig {
    linked_folders: HashMap<String, String>,
}

fn config_path(app: &AppHandle) -> Result<PathBuf, String> {
    let dir = app
        .path()
        .app_config_dir()
        .map_err(|e| format!("Failed to get config directory: {e}"))?;

    fs::create_dir_all(&dir).map_err(|e| format!("Failed to create config directory: {e}"))?;

    Ok(dir.join("config.json"))
}

fn load_config(app: &AppHandle) -> Result<AppConfig, String> {
    let path = config_path(app)?;

    if !path.exists() {
        return Ok(AppConfig::default());
    }

    let contents = fs::read_to_string(&path).map_err(|e| format!("Failed to read config: {e}"))?;

    serde_json::from_str(&contents).map_err(|e| format!("Failed to parse config: {e}"))
}

fn save_config(app: &AppHandle, config: &AppConfig) -> Result<(), String> {
    let path = config_path(app)?;

    let contents = serde_json::to_string_pretty(config)
        .map_err(|e| format!("Failed to serialize config: {e}"))?;

    fs::write(&path, contents).map_err(|e| format!("Failed to write config: {e}"))
}

fn get_folder_for_processor(app: &AppHandle, nickname: &str) -> Result<PathBuf, String> {
    let mut config = load_config(app)?;

    if let Some(folder) = config.linked_folders.get(nickname) {
        let path = PathBuf::from(folder);

        if path.is_dir() {
            return Ok(path);
        }

        // The previously linked folder no longer exists.
        config.linked_folders.remove(nickname);
        save_config(app, &config)?;
    }

    let selected = app
        .dialog()
        .file()
        .set_title(format!("Select project folder for {nickname}"))
        .blocking_pick_folder();

    let selected = selected.ok_or_else(|| "No folder selected".to_string())?;

    let folder = selected
        .as_path()
        .ok_or_else(|| "Selected path is invalid".to_string())?
        .to_path_buf();

    config
        .linked_folders
        .insert(nickname.to_string(), folder.to_string_lossy().into_owned());

    save_config(app, &config)?;

    Ok(folder)
}

#[tauri::command]
async fn deploy(app: AppHandle, hostname: String, nickname: String) -> Result<(), String> {
    let folder = get_folder_for_processor(&app, &nickname)?;

    deploy_cmd(&folder, &hostname)
}

fn find_python(folder: &Path) -> PathBuf {
    #[cfg(target_os = "windows")]
    {
        for name in [".venv", "venv"] {
            let python = folder.join(name).join("Scripts").join("python.exe");

            if python.is_file() {
                return python;
            }
        }

        PathBuf::from("python")
    }

    #[cfg(not(target_os = "windows"))]
    {
        for name in [".venv", "venv"] {
            let python = folder.join(name).join("bin").join("python");

            if python.is_file() {
                return python;
            }
        }

        PathBuf::from("python3")
    }
}

fn deploy_cmd(folder: &Path, hostname: &str) -> Result<(), String> {
    let python = find_python(folder);

    println!(
        "Running synapse installer with Python: {}",
        python.display()
    );

    let status = Command::new(&python)
        .arg("-m")
        .arg("synapse_installer")
        .arg("install")
        .arg(hostname)
        .current_dir(folder)
        .status()
        .map_err(|e| {
            format!(
                "Failed to run synapse_installer using '{}': {e}",
                python.display()
            )
        })?;

    if !status.success() {
        return Err(format!("synapse_installer exited with status: {}", status));
    }

    Ok(())
}

#[tauri::command]
fn get_linked_folder(app: AppHandle, nickname: String) -> Result<Option<String>, String> {
    let config = load_config(&app)?;

    Ok(config.linked_folders.get(&nickname).cloned())
}

#[tauri::command]
fn unlink_folder(app: AppHandle, nickname: String) -> Result<(), String> {
    let mut config = load_config(&app)?;

    config.linked_folders.remove(&nickname);

    save_config(&app, &config)
}

#[tauri::command]
fn open_linked_folder(app: AppHandle, nickname: String) -> Result<(), String> {
    let config = load_config(&app)?;

    let folder = config
        .linked_folders
        .get(&nickname)
        .ok_or_else(|| format!("No folder is linked to processor '{nickname}'"))?;

    let path = PathBuf::from(folder);

    if !path.is_dir() {
        return Err("Linked folder does not exist".to_string());
    }

    app.opener()
        .open_path(path.to_string_lossy().to_string(), None::<String>)
        .map_err(|e| format!("Failed to open linked folder: {e}"))
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![
            udp::scan_devices,
            deploy,
            get_linked_folder,
            unlink_folder,
            open_ssh_terminal,
            open_linked_folder
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
