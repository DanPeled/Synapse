---
description: Install Synapse on your development computer and on a coprocessor.
icon: down-to-line
---

# Installing Software

Installing Synapse has two parts:

1. **Your development computer** — installs the `synapsefrc` package, which includes the runtime, the installer, and the web UI.
2. **Your coprocessor** — gets a Python environment and runs the runtime as a systemd service.

You do not install Synapse on the RoboRIO. Robot code uses [SynapseLib](../robot-interfacing/synapse-bridge/README.md) instead.

## Development computer installation

### Requirements

- Python 3.11–3.14.
- `pip`.
- Git (only needed if you install from source).
- SSH access to the coprocessor.

{% hint style="tip" %}
Use a virtual environment so Synapse's pinned dependencies do not interfere with other Python projects.
{% endhint %}

```bash
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
```

### Install the package

```bash
python -m pip install --upgrade synapsefrc
```

Verify the install:

```bash
python -m synapse_installer --help
```

```text
Usage: python -m synapse_installer <command> [options]

Commands:
  create       Create a new project
  deploy       Deploy the project
  sync         Sync files or data
  install      Run sync then deploy
  device       Device actions (e.g. `add`)
```

The installer is also available as the `synapse_installer` command on your `PATH`.

### Install from source

Use this if you are developing Synapse itself or need an unreleased change.

```bash
git clone https://github.com/DanPeled/Synapse.git
cd Synapse
python -m pip install -e .
```

## Coprocessor installation

You do not need to copy Synapse onto the device by hand. The `sync` step installs it over SSH. The device only needs:

- A 64-bit Linux distribution.
- SSH enabled.
- Internet access for the first install.
- `sudo` access for the SSH user.

The installer will:

- Install system packages: `libopencv-dev`, `unzip`, and `isc-dhcp-client`.
- Find a compatible Python interpreter (3.11–3.14).
- Build Python 3.12.2 from source if no compatible interpreter exists. This takes a long time on slower devices.
- Create a virtual environment at `~/.venv`.
- Install the Python requirements.
- Create a systemd service named `synapse-runtime`.
- Enable and start the service.

{% hint style="warning" %}
Building Python from source can take 20–60 minutes on a Pi. A distribution image that already includes Python 3.11 through 3.14 avoids this.
{% endhint %}

### Imaging a device

{% hint style="info" %}
There are currently no official Synapse device images. Any minimal 64-bit Debian/Ubuntu-based Linux image with SSH should work.
{% endhint %}

Recommended imaging tool: [Balena Etcher](https://etcher.balena.io/).

Suggested images:

- **Orange Pi 5** — [Armbian Bookworm 25.5.1](https://distrohub.kyiv.ua/armbian-dl/orangepi5/archive/Armbian_25.5.1_Orangepi5_bookworm_vendor_6.1.115_minimal.img.xz)
- **Raspberry Pi 5** — [Armbian for Raspberry Pi](https://www.armbian.com/rpi4b/) (instructions included on the download page)

After imaging:

1. Boot the device.
2. Connect it to your network. See [Networking](quick-start/networking.md).
3. Enable SSH if it is not enabled by default.
4. Confirm you can connect:

```bash
ssh <username>@<device-ip>
```

### Deploy your first project

On your development computer, create a project and install it:

```bash
python -m synapse_installer create
cd <project-name>
python -m synapse_installer install <device-nickname>
```

The installer asks for the device hostname, IP address, and SSH password, then saves them in `.synapseproject`. The nickname defaults to the hostname.

Pass the nickname to `install` or `sync` so they target the right device. To target several devices, list each nickname:

```bash
python -m synapse_installer install <nickname-1> <nickname-2>
```

### Verify the runtime

On the device:

```bash
sudo systemctl status synapse-runtime
```

You should see `active (running)`. To follow logs:

```bash
journalctl -u synapse-runtime -f
```

Then open the dashboard:

```text
http://<device-ip>:3000
```

## Updating Synapse

Update the package on your development computer:

```bash
python -m pip install --upgrade synapsefrc
```

Then re-deploy your project:

```bash
python -m synapse_installer install <device-nickname>
```

The deploy step preserves the device's `config/` folder, so calibrated cameras and tuned settings survive an update.

## Uninstalling

On the device:

```bash
sudo systemctl stop synapse-runtime
sudo systemctl disable synapse-runtime
sudo rm /etc/systemd/system/synapse-runtime.service
sudo systemctl daemon-reload
rm -rf ~/Synapse ~/.venv
```

On your development computer:

```bash
python -m pip uninstall synapsefrc
```

## Next steps

- [Quick Start](quick-start/README.md)
- [Project Management](../usage/project-management/README.md)
- [Networking](quick-start/networking.md)
- [Troubleshooting](../additional-resources/troubleshooting.md)
