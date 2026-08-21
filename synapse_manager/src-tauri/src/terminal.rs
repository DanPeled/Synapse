use std::process::Command;

#[tauri::command]
pub fn open_ssh_terminal(ip: String, username: String) -> Result<(), String> {
    let target = format!("{}@{}", username, ip);

    // Explicit terminal selected by the user.
    if let Ok(terminal) = std::env::var("TERMINAL") {
        if !terminal.is_empty() {
            return launch_terminal(&terminal, &["ssh", &target]);
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

            command.arg("ssh");
            command.arg(&target);

            if command.spawn().is_ok() {
                return Ok(());
            }
        }
    }

    Err("Could not find a supported terminal emulator".to_string())
}

fn command_exists(command: &str) -> bool {
    Command::new("sh")
        .arg("-c")
        .arg(format!("command -v {}", shell_escape(command)))
        .output()
        .map(|output| output.status.success())
        .unwrap_or(false)
}

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

fn shell_escape(value: &str) -> String {
    format!("'{}'", value.replace('\'', "'\\''"))
}
