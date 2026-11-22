use std::process::Command;

#[tauri::command]
pub fn open_ssh_terminal(ip: String, username: String) -> Result<(), String> {
    let target = format!("{}@{}", username, ip);

    #[cfg(target_os = "windows")]
    return open_windows_terminal(&target);

    #[cfg(target_os = "macos")]
    return open_macos_terminal(&target);

    #[cfg(not(any(target_os = "windows", target_os = "macos")))]
    open_linux_terminal(&target)
}

#[cfg(target_os = "windows")]
fn open_windows_terminal(target: &str) -> Result<(), String> {
    // Windows Terminal, if installed, gives a much better experience.
    for launcher in ["wt", "cmd"] {
        let mut command = Command::new(launcher);
        if launcher == "wt" {
            command.args(["new-tab", "cmd", "/k", "ssh"]);
        } else {
            command.args(["/c", "start", "cmd", "/k", "ssh"]);
        }
        command.arg(target);
        if command.spawn().is_ok() {
            return Ok(());
        }
    }
    Err("Could not launch a terminal for SSH".to_string())
}

#[cfg(target_os = "macos")]
fn open_macos_terminal(target: &str) -> Result<(), String> {
    // `open -a Terminal` works without an AppleScript permission prompt on
    // modern macOS when passing the ssh command as arguments.
    let script = format!(
        "tell application \"Terminal\" to do script \"ssh {}\"",
        target.replace('\\', "\\\\").replace('"', "\\\"")
    );
    let mut command = Command::new("osascript");
    command.arg("-e").arg(script);
    command
        .spawn()
        .map_err(|e| format!("Failed to launch Terminal: {e}"))?;
    Ok(())
}

#[cfg(not(any(target_os = "windows", target_os = "macos")))]
fn open_linux_terminal(target: &str) -> Result<(), String> {
    // Explicit terminal selected by the user.
    if let Ok(terminal) = std::env::var("TERMINAL") {
        if !terminal.is_empty() {
            return launch_terminal(&terminal, &["ssh", target]);
        }
    }

    // Common Linux terminal emulators.
    let terminals: &[(&str, &[&str])] = &[
        ("ptyxis", &["--"]),
        ("gnome-terminal", &["--"]),
        ("konsole", &["-e"]),
        ("kitty", &[]),
        ("alacritty", &["-e"]),
        ("xfce4-terminal", &["-e"]),
        ("mate-terminal", &["--"]),
        ("lxterminal", &["-e"]),
        ("terminator", &["-e"]),
    ];

    for (terminal, prefix) in terminals {
        if command_exists(terminal) {
            let mut command = Command::new(terminal);

            for arg in *prefix {
                command.arg(arg);
            }

            command.arg("ssh").arg(target);

            if command.spawn().is_ok() {
                return Ok(());
            }
        }
    }

    Err("Could not find a supported terminal emulator".to_string())
}

#[cfg(not(any(target_os = "windows", target_os = "macos")))]
fn command_exists(command: &str) -> bool {
    Command::new("sh")
        .arg("-c")
        .arg(format!("command -v {}", shell_escape(command)))
        .output()
        .map(|output| output.status.success())
        .unwrap_or(false)
}

#[cfg(not(any(target_os = "windows", target_os = "macos")))]
fn launch_terminal(terminal: &str, args: &[&str]) -> Result<(), String> {
    let mut command = Command::new(terminal);

    for arg in args {
        command.arg(arg);
    }

    command
        .spawn()
        .map_err(|e| format!("Failed to launch terminal: {e}"))?;

    Ok(())
}

#[cfg(not(any(target_os = "windows", target_os = "macos")))]
fn shell_escape(value: &str) -> String {
    format!("'{}'", value.replace('\'', "'\\''"))
}
