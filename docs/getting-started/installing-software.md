---
description: Install Synapse on your development computer and on a coprocessor.
icon: down-to-line
---

# Installing Software

Installing Synapse has two parts:

1. **Your development computer** — installs the `synapsefrc` package, which includes the runtime, the installer, and the web UI.
2. **Your coprocessor** — gets a Python environment and runs the runtime as a systemd service.

You do not install Synapse on the robot controller. Robot code uses [SynapseLib](../robot-interfacing/synapse-bridge/README.md) instead.

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
Usage: python -m synapse_installer <command> [options] [devices...]

Commands:
  create       Create a new project
  deploy       Deploy the project to one or more devices
  sync         Install or update Python dependencies on devices
  install      Run sync, then deploy
  device       Manage devices (add, list, remove)

Deploy/install options:
  -y, --yes        Don't ask for confirmation before deploying
  -n, --dry-run    Show the deployment targets without changing anything
      --no-logs    Don't follow the runtime logs after deploying

If no device names are given, deploy and install use every configured device.
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

- Verify the device's SSH host key. On the first connection it shows a SHA-256 fingerprint and asks you to trust it, then saves the key in `~/.ssh/known_hosts`.
- Configure passwordless sudo for the SSH user in `/etc/sudoers.d/<username>-nopasswd`.
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

{% hint style="info" %}
Non-interactive runs, such as CI or a GUI launcher, reject an unknown SSH host key instead of prompting. Connect once with `ssh <user>@<device-ip>` or run `install` from a terminal to trust the key.
{% endhint %}

### Device images

The [2027 alpha release](https://github.com/DanPeled/Synapse/releases/tag/v2027.0.0a1) publishes prebuilt images and overlays with the Synapse runtime, a sample project, passwordless `sudo`, and the `synapse-runtime` systemd service already set up.

Flashable images:

- **Raspberry Pi 5** — `synapse-raspberrypi-<version>-raspios-bookworm-arm64.img.xz`
- **Orange Pi 5 / 5 Plus / 5 Max** — `synapse-orangepi5{,-plus,-max}-<version>-armbian-bookworm.img.xz`
- **Radxa Rock 5B** — `synapse-rock-5b-<version>-armbian-bookworm.img.xz`

Overlays for systems that need their own OS image:

- **Jetson (JetPack/L4T)** — `synapse-jetson-overlay-<version>.tar.gz`
- **x86_64 mini PCs** — `synapse-x86_64-overlay-<version>.tar.gz`

NVIDIA does not allow redistribution of a complete JetPack/L4T image, and x86 mini PCs normally ship without an OS. For those targets, install JetPack/L4T or Ubuntu Server 24.04 first, then extract the matching overlay:

```bash
sudo tar -xzf synapse-<target>-overlay-<version>.tar.gz -C /
sudo /opt/synapse-build/install.sh
```

The overlay's first-boot service also installs the runtime and places the sample project in the first regular user's home directory. First boot needs internet access to download Python dependencies.

{% hint style="info" %}
These images are alpha artifacts. For other hardware, any minimal 64-bit Debian/Ubuntu-based Linux image with SSH should work. A recommended imaging tool is [Balena Etcher](https://etcher.balena.io/).
{% endhint %}

After imaging or applying an overlay:

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

The installer asks for the device hostname, IP address, and SSH password, then saves them in `.synapseproject`. The nickname defaults to the hostname. You can enter these manually or let `device add` discover devices on the network; automatic discovery uses the name the runtime reports as the nickname.

Pass the nickname to `install` or `sync` so they target the right device. To target several devices, list each nickname:

```bash
python -m synapse_installer install <nickname-1> <nickname-2>
```

If you leave out the names, `install` uses every configured device. Before deploying, it asks for confirmation unless you pass `--yes`. Add `--dry-run` to preview the targets, or `--no-logs` to stop after the service starts. If the sync step fails, `install` prints `Sync failed; skipping deployment.` and does not change the project on the device.

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

The deploy step preserves the device's `config/` folder, so calibrated cameras and tuned settings survive an update. Deployments are staged and validated: if the new version fails to start, the installer restores the previous deployment and restarts it.

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
