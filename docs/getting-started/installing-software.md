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

The [2027 alpha release](https://github.com/DanPeled/Synapse/releases/tag/v2027.0.0a1) publishes prebuilt images and overlays. They are built from the release wheel, so the runtime and dashboard match the release tag.

#### What is preinstalled

Every image uses the same layout:

| Item | Location |
| --- | --- |
| Sample project | `$HOME/Synapse` |
| Python virtual environment | `$HOME/.venv` |
| systemd service | `synapse-runtime` |
| Passwordless `sudo` rule | `/etc/sudoers.d/90-synapse-<user>` |

The sample project starts without a camera. Replace it with a real project using `python -m synapse_installer deploy` when you are ready.

#### Flashable images

| Device | Release asset | Notes |
| --- | --- | --- |
| Raspberry Pi 3/4/5, Zero 2 W (64-bit) | `synapse-raspberrypi-<version>-raspios-bookworm-arm64.img.xz` | Raspberry Pi OS Bookworm |
| Orange Pi 5 / 5 Plus / 5 Max | `synapse-orangepi5-<version>-armbian-bookworm.img.xz`, `synapse-orangepi5-plus-<version>-armbian-bookworm.img.xz`, `synapse-orangepi5-max-<version>-armbian-bookworm.img.xz` | Armbian Bookworm |
| Radxa Rock 5B | `synapse-rock-5b-<version>-armbian-bookworm.img.xz` | Armbian Bookworm |

Use [Balena Etcher](https://etcher.balena.io/) or your board's normal flashing tool to write the `.img.xz` archive to a microSD card or SSD. Etcher can write the compressed file directly.

#### Linux overlays

| Device | Release asset | Notes |
| --- | --- | --- |
| Jetson (JetPack/L4T) | `synapse-jetson-overlay-<version>.tar.gz` | NVIDIA does not permit redistribution of a complete JetPack/L4T image |
| x86_64 mini PCs (Beelink, Intel NUC, and similar) | `synapse-x86_64-overlay-<version>.tar.gz` | Install Ubuntu Server 24.04 first |

An overlay does not replace the operating system. Install JetPack/L4T or Ubuntu Server 24.04 first, then extract the matching overlay on the running device:

```bash
sudo tar -xzf synapse-<target>-overlay-<version>.tar.gz -C /
sudo /opt/synapse-build/install.sh
```

The overlay's `synapse-firstboot.service` finds the first regular user, provisions the runtime for that user, and disables itself after a successful run. It does not create a new user. First boot needs internet access to download Python dependencies, and the rootfs must provide Python 3.11 or newer (JetPack 7 / Ubuntu 24.04 or later).

#### Default credentials

| Image | SSH user | Password |
| --- | --- | --- |
| Raspberry Pi | `pi` | `synapse` |
| Armbian | `synapse` | `synapse` |

Linux overlays use the first regular user already on the system and do not set a password.

{% hint style="warning" %}
Change the default password before putting a device on an untrusted network. The images intentionally include a passwordless `sudo` rule because the installer requires `sudo -n true` to deploy, so a compromised runtime user has root-equivalent access.
{% endhint %}

#### First boot

Images keep DHCP enabled so the device can reach the internet, DNS, and a default gateway. To make it reachable at a predictable robot-network address, set an optional static address under **Settings > Network Settings**. It is added as a secondary address while DHCP stays enabled. See [Settings Page](../usage/built-in-pipelines-1/settings-page.md#dhcp-and-static-addresses).

1. Flash the image or apply the overlay as described above.
2. Boot the device and connect it to your network. See [Networking](quick-start/networking.md).
3. Find its IP address from your router, or run `hostname -I` on the device.
4. Connect over SSH using the credentials from the table above:

   ```bash
   ssh <username>@<device-ip>
   ```

5. Change the password with `passwd`, then confirm the runtime is running:

   ```bash
   sudo -n true
   sudo systemctl status synapse-runtime
   ```

6. Open the dashboard at `http://<device-ip>:3000`.

{% hint style="info" %}
These images are alpha artifacts. For other hardware, any minimal 64-bit Debian/Ubuntu-based Linux image with SSH should work. See [Deploying on Custom Hardware](hardware-selection/deploying-on-custom-hardware.md) for the full requirements.
{% endhint %}

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
