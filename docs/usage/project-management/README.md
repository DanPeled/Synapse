---
description: Create, configure, and deploy a Synapse project.
icon: hands-holding-circle
---

# Project Management

A Synapse project is a folder containing your pipelines, configuration, and deployment targets. It is separate from your robot code project.

## Create a project

From the folder where you want the project to live:

```bash
python -m synapse_installer create
```

The interactive prompt asks for:

1. A **project name**. Synapse creates a folder with this name.
2. Whether to **set up coprocessor info** now.

If you choose to set up a coprocessor, you can add it **manually** or let the installer **find devices automatically**.

Manual setup asks for:

- The device **hostname** (the SSH username).
- A **nickname** used by the CLI and Synapse Manager.
- The device **IP address**.
- The SSH **password**.

Automatic setup sends a UDP discovery ping on port `45454` and lists the devices whose runtime answers. It asks you to confirm each device and enter its SSH password. The nickname defaults to the name the runtime reports. The runtime must already be running, and your computer must be on the same subnet as the device.

You can skip this and add devices later.

### Generated files

```text
<project-name>/
├── .synapseproject
├── main.py
├── pyproject.toml
├── pipelines/
│   └── (your custom pipelines)
└── deploy/
    └── readme.md
```

The `config/` folder is created by the runtime on first start, not by `create`.

### `main.py`

`main.py` starts the runtime:

```python
import os
from pathlib import Path

from synapse.core.synapse import Synapse

if __name__ == "__main__":
    Synapse.createAndRunRuntime(root=Path(os.getcwd()))
```

{% hint style="warning" %}
The current `create` command still writes the older import `from synapse.core import Synapse`, which raises `ImportError`. Change it to `from synapse.core.synapse import Synapse` before running or deploying the project.
{% endhint %}

`createAndRunRuntime` accepts a second argument:

```python
Synapse.createAndRunRuntime(root=Path(os.getcwd()), sendSettingsInNT=False)
```

When `sendSettingsInNT=True`, the runtime also publishes pipeline settings under `<camera>/settings` in NetworkTables. This is off by default.

### `pyproject.toml`

The generated file contains project metadata. You can add Python packages that your custom pipelines need:

```toml
[tool.synapse]
requires = [
    "onnxruntime",
    "ultralytics",
]
```

During `sync`, Synapse installs these packages on the coprocessor in addition to its own requirements.

### `.synapseproject`

This file stores the project name and deploy targets:

```yaml
name: my-vision-project
deploy:
  orangepi:
    hostname: orangepi
    ip: 10.0.0.20
    password: your-ssh-password
```

{% hint style="danger" %}
The SSH password is stored in plain text in `.synapseproject`. Do not commit this file to a public repository. Add `.synapseproject` to `.gitignore` if your repository is public.
{% endhint %}

When the installer saves device information, it writes `.synapseproject` with owner-only permissions (`0600`). If an existing file is readable by other users, the installer prints a warning; run `chmod 600 .synapseproject` to fix it.

## Add or remove devices

```bash
python -m synapse_installer device add
python -m synapse_installer device list
python -m synapse_installer device remove <nickname>
```

`device add` offers the same manual and automatic choices as project creation. `device list` prints each configured nickname and address. `device remove` asks for confirmation before deleting the entry.

You can also edit the `deploy` section of `.synapseproject` directly. Each entry must contain `hostname` (the SSH username), `ip`, and `password`. The installer rejects entries with missing fields, whitespace in the hostname, or an invalid IP address.

## Deploy commands

Run these commands from inside the project folder.

| Command | What it does |
| --- | --- |
| `python -m synapse_installer sync [devices...]` | Installs system packages and Python dependencies. Without names, syncs every configured device |
| `python -m synapse_installer deploy [options] [devices...]` | Packages, validates, and deploys the project. Without names, deploys to every configured device after confirmation |
| `python -m synapse_installer deploy <nickname>` | Deploys to one device without the "all devices" confirmation |
| `python -m synapse_installer install [options] [devices...]` | Runs `sync`, then `deploy`. If sync fails, deployment is skipped |

### Deploy options

| Option | Effect |
| --- | --- |
| `-y`, `--yes` | Skip the confirmation prompt when deploying to every device |
| `-n`, `--dry-run` | Print the selected targets and exit without packaging, uploading, or changing services |
| `--no-logs` | Do not follow the runtime logs after a successful deploy |
| `--help` | Show the command usage |

`deploy` and `install` target every configured device when you do not list names. Before deploying, they ask for confirmation unless you pass `--yes`. In a non-interactive terminal (CI, scripts, or a GUI launcher), they refuse to deploy to every device without `--yes`. Naming one or more devices skips the confirmation.

`sync` and `install` return a non-zero exit code if any device fails. `install` prints `Sync failed; skipping deployment.` instead of deploying when the sync step fails. `deploy` continues with the remaining devices after a failure, then reports how many deployments failed.

### What gets deployed

The deploy step packages:

- Every `.py` file in the project.
- Everything inside the `deploy/` folder.

Before it connects to any device, the installer checks that `build/project.zip` and `build/synapse.zip` exist, are non-empty ZIP files, contain no absolute paths, `..` segments, or symbolic links, and that `project.zip` contains `main.py`. A broken package fails before the device is touched.

On each device it:

1. Verifies the SSH host key. On the first connection the installer shows a SHA-256 fingerprint and asks you to trust it; the key is saved in `~/.ssh/known_hosts`.
2. Checks that `unzip` and passwordless `sudo` are available.
3. Uploads the archives to a temporary directory and extracts them into `~/.synapse-staging-<timestamp>-<pid>`.
4. Stops the `synapse-runtime` service.
5. Copies the existing `~/Synapse/config` folder into the staging directory.
6. Moves `~/Synapse` to `~/.synapse-backup-<timestamp>-<pid>`, then moves the staging directory into place as `~/Synapse`.
7. Writes and enables the `synapse-runtime` service, starts it, and waits up to 20 seconds for systemd to report it active.
8. On success, keeps that backup, removes older `.synapse-backup-*` folders, deletes temporary files, and streams the runtime logs unless you passed `--no-logs`.

If the swap or a later step fails, the installer restores the backup and restarts the previous deployment. If there was no previous deployment, it removes the failed files. If it fails after stopping the service but before the swap, it restarts the existing deployment. The command exits non-zero and prints the failure. Because `config/` is copied into the new deployment, calibration data and tuned settings survive a deploy.

The backup is kept at `~/.synapse-backup-<timestamp>-<pid>` on the device. Only the most recent backup is kept automatically; remove it manually if you need disk space.

After a successful deploy the command follows the runtime logs. Press `Ctrl+C` to stop following them; the deployment is already complete and the service keeps running. Pass `--no-logs` to skip this step.

{% hint style="warning" %}
Non-interactive runs reject an unknown SSH host key instead of prompting. Connect once with `ssh <user>@<device-ip>` or run `install` from a terminal to trust the key, then retry. If a device was reflashed, remove its old key from `~/.ssh/known_hosts` before deploying.
{% endhint %}

Set `SYNAPSE_DEBUG=1` to print a full Python traceback when a deployment fails.

### What gets synced

The `sync` step:

- Configures passwordless sudo for the SSH user by writing `/etc/sudoers.d/<username>-nopasswd` (mode `440`) when `sudo -n true` does not already succeed. The username must contain only letters, digits, `_`, `.`, or `-`; otherwise sync refuses to edit sudoers.
- Installs `libopencv-dev`, `unzip`, and `isc-dhcp-client`.
- Finds Python 3.11–3.14, or builds Python 3.12.2 if none exists.
- Creates a virtual environment at `~/.venv`.
- Installs Synapse's requirements and any packages listed in `pyproject.toml`.
- Returns a non-zero exit code if any device fails.

Run `sync` again when you add dependencies. You do not need to run it for every code change.

## Project folders

### `pipelines/`

Place custom pipelines here. Synapse discovers every file ending in `_pipeline.py` recursively.

```text
pipelines/
├── my_pipeline.py
└── helpers/
    └── another_pipeline.py
```

Class names become pipeline types unless you use the `@pipelineName` or `@systemPipeline` decorators. Use `@disabled` to hide a pipeline from the UI.

See [Custom Pipelines](../custom-pipelines/README.md).

### `deploy/`

Files in this folder are uploaded to the coprocessor and are available to your pipeline at runtime. Common uses:

- AprilTag field maps (`fmap.json`).
- Model files (`.onnx`, `.tflite`).
- Lookup tables and calibration files.

Access them with `synapse.hardware.deploy_dir.DeployDirectory`.

### `config/`

Created and managed by the runtime on the device. It contains:

```text
config/
├── settings.yml
├── camera_0/
│   ├── camera_configs.yml
│   └── pipeline_settings.yml
└── camera_1/
    └── ...
```

Do not edit these files while the runtime is running. Changes may be overwritten when settings are saved.

## Running the project locally

```bash
python main.py
```

Useful flags:

```bash
python main.py --server      # start a local NetworkTables server
python main.py --sim         # use simulated cameras
python main.py --headless    # skip the terminal UI
```

See [Working without a robot](../working-without-a-robot.md).

## Using Synapse Manager

If you prefer a desktop app over the CLI, see [Synapse Manager](synapse-manager.md). It can discover devices, open dashboards, and deploy linked project folders.

## Next steps

- [Synapse Manager](synapse-manager.md)
- [Custom Pipelines](../custom-pipelines/README.md)
- [UI Interaction](../built-in-pipelines-1/README.md)
- [Installing Software](../../getting-started/installing-software.md)
