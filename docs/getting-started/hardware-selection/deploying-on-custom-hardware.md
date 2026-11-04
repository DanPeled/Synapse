---
description: Requirements a Linux device must meet to run the Synapse runtime and receive deployments.
icon: server
---

# Deploying on Custom Hardware

Synapse is not limited to the hardware listed elsewhere in these docs. Any Linux device can work if it meets the requirements below.

## Operating system

- A 64-bit Linux distribution (ARM64 or x86_64).
- A Debian/Ubuntu family distribution is easiest, because the installer uses `apt` for system packages. Other distributions work if you install the equivalent packages manually.
- A minimal/server image is preferred. A desktop environment is not required.

## Required software

The installer's `sync` step expects:

| Requirement | Why it is needed |
| --- | --- |
| A package manager (`apt`, `dnf`, `yum`, `pacman`, or `apk`) | To install OpenCV and other system libraries |
| **OpenCV system libraries** (`libopencv-dev` on Debian/Ubuntu) | Image processing |
| **Python 3.11–3.14** | The runtime and its dependencies |
| `pip` and `venv` | Python environment on the device |
| **SSH server** | The installer connects over SSH to deploy and configure the device |
| `sudo` for the SSH user | Install packages and create the systemd service |
| **systemd** | Runs the runtime as `synapse-runtime` |
| `netplan` and `dhclient` | Optional, but needed for static IP configuration from the UI |

If Python 3.11–3.14 is not installed, the installer builds Python 3.12.2 from source. This requires build tools and can take a long time. Installing a compatible Python through the distribution's package manager is much faster.

## Network requirements

- The device must be reachable from your development computer over SSH.
- The device needs internet access during the first `sync` so packages can be downloaded.
- Ports used by the runtime:

| Port | Purpose |
| --- | --- |
| `22` | SSH / deployment |
| `3000` | Web UI |
| `8765` | UI WebSocket |
| `1180` and up | Camera streams (CameraServer) |
| `45454/udp` | Device discovery for Synapse Manager |

## Permissions

The SSH user must be able to run `sudo`. During `sync`, the installer adds a sudoers rule that lets the SSH user run commands without a password (`NOPASSWD:ALL`).

## Camera support

- **USB cameras** must appear as a V4L2 device (`/dev/video*`).
- **CSI cameras** need the correct device-tree overlay and driver for your board.
- Check that the camera works with OpenCV before deploying.

## Verifying a custom device

Before deploying, run these checks on the device:

```bash
# Python version
python3 --version

# OpenCV system libraries
ldconfig -p | grep opencv

# SSH
systemctl status ssh

# sudo
sudo -v

# Camera (USB)
ls /dev/video*
```

Then from your project folder on the development computer:

```bash
python -m synapse_installer sync <device-nickname>
```

If sync completes successfully, deploy:

```bash
python -m synapse_installer deploy <device-nickname>
```

## Troubleshooting

- **`No compatible Python found`** — install Python 3.11–3.14 through the package manager, or wait for the source build to finish.
- **`libopencv-dev` missing** — install it manually, or switch to a Debian/Ubuntu image.
- **Permission denied over SSH** — confirm the username and password, and make sure SSH is enabled.
- **Service does not start** — check `journalctl -u synapse-runtime -f`.

See [Troubleshooting](../../additional-resources/troubleshooting.md) for more.
