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

If you choose to set up a coprocessor, you are asked for:

- The device **hostname** (the SSH username).
- A **nickname** used by the CLI and Synapse Manager.
- The device **IP address**.
- The SSH **password**.

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

## Add a device

```bash
python -m synapse_installer device add
```

You can also edit the `deploy` section of `.synapseproject` directly.

## Deploy commands

Run these commands from inside the project folder.

| Command | What it does |
| --- | --- |
| `python -m synapse_installer sync <nickname>` | Installs system packages and Python dependencies on the device |
| `python -m synapse_installer deploy` | Copies the project to every configured device and restarts the runtime |
| `python -m synapse_installer deploy <nickname>` | Copies the project to one device |
| `python -m synapse_installer install <nickname>` | Runs `sync`, then `deploy`, for the named device |

{% hint style="info" %}
Pass device names to `sync` and `install`. When they run without a name, the sync step falls back to the installer's own process arguments and reports `No device named ... found`. `deploy` without names still targets every device. See [Known Issues](../../additional-resources/known-issues.md#sync-and-install-need-an-explicit-device-name).
{% endhint %}

### What gets deployed

The deploy step uploads:

- Every `.py` file in the project.
- Everything inside the `deploy/` folder.

On the device it:

1. Creates `~/Synapse/config` if it does not exist.
2. Deletes everything else in `~/Synapse`.
3. Uploads and unzips the project.
4. Installs or updates the `synapse-runtime` systemd service.
5. Restarts the service and streams its logs to your terminal.

Because `config/` is preserved, calibration data and tuned settings survive a deploy.

### What gets synced

The `sync` step:

- Installs `libopencv-dev`, `unzip`, and `isc-dhcp-client`.
- Finds Python 3.11–3.14, or builds Python 3.12.2 if none exists.
- Creates a virtual environment at `~/.venv`.
- Installs Synapse's requirements and any packages listed in `pyproject.toml`.

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
