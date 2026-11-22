# Synapse device images

This directory builds OS images and rootfs overlays with the Synapse runtime
preinstalled and a sample project already deployed. Images are produced by the
`Build Synapse Device Images` workflow on every `v*` tag and can also be built
locally.

## What is in an image

Every image uses the same layout:

| Item | Path |
| --- | --- |
| Sample project | `$HOME/Synapse` |
| Python virtualenv | `$HOME/.venv` |
| systemd service | `synapse-runtime` |
| Passwordless sudo | `/etc/sudoers.d/90-synapse-<user>` |

The service runs `$HOME/.venv/bin/python $HOME/Synapse/main.py` as the image's
runtime user. The sample project starts without a camera and can be replaced
with a real project through `python -m synapse_installer deploy`.

The image also contains a passwordless sudo rule for the runtime user because
the installer requires `sudo -n true` before it will deploy.

## Network configuration

Every image keeps DHCP enabled on its interfaces. That is what lets a
coprocessor get internet access, DNS, and a default gateway when it is plugged
into an internet-connected router.

To make the device reachable at a predictable address on the robot network, set
an optional static IPv4 address in the Synapse UI under **Settings > Network
Settings**. The address is added as a secondary address; DHCP is never turned
off, so both the router-assigned address and the static address stay usable.

- The default FRC address for a team is `10.TE.AM.11`. For example, team `1234`
  uses `10.12.34.11` and team `68` uses `10.0.68.11`.
- The prefix length defaults to `/24` and can be edited in the UI.
- Loopback, container, VM, and VPN interfaces such as `lo`, `docker0`, and
  `tailscale0` are hidden because they cannot carry a robot-network address.
- Changes apply immediately and may briefly drop the connection to the device.
  The UI warns before applying them.

The runtime persists the address in `$HOME/Synapse/config/settings.yml` and
reapplies it on startup. On devices that use NetworkManager, the address is
added to the active connection profile with `nmcli`. Devices without
NetworkManager use a `netplan` drop-in, and anything else falls back to
`ip addr` with a worker that reapplies the address if the interface is reset.
All of these paths keep DHCP enabled.

## Direct USB / Ethernet connection (USB gadget mode)

On boards with a USB device-mode controller (Raspberry Pi 4/Zero 2 W, RK3588
boards such as Orange Pi 5 and Radxa Rock 5B), images install and enable a
`synapse-usb-gadget` service. Plug a USB cable from the computer into the
coprocessor's device-mode port and the board presents a composite USB device:

- **USB Ethernet** (ECM, NCM, or RNDIS, chosen from what the kernel provides)
  for SSH, deploy, dashboard, and file transfer. The gadget uses an IPv4
  link-local address (`169.254.x.x`), which Windows, macOS, and Linux assign
  automatically. No computer-side network configuration is required.
- **USB Mass Storage** with a small FAT image containing connection details and
  a drop folder.

The resolver derives a stable link-local address from the board's serial, so the
device keeps the same address across reboots. Discovery broadcasts on all host
interfaces and the responder returns an address on the link the ping arrived
over, so `python -m synapse_installer device add` finds USB-connected devices
without router networking.

Everything is discovered at runtime via `Platform` and configfs: the UDC name,
function, network interface, and address are never hard-coded. Unsupported
boards (for example x86_64 mini PCs) skip gadget startup cleanly and continue to
work over ordinary Ethernet.

To disable installation of the gadget service, pass `--no-usb-gadget` to
`provision.sh`.

## Platform registry

`synapse_imager/platforms.ini` is the single place to add a board. Each
`[target.<id>]` section becomes one entry in the release workflow matrix, so
adding a board does not require editing the workflow.

List the supported platforms and targets:

```bash
bash synapse_imager/build.sh list
```

Build one target locally:

```bash
make build
bash synapse_imager/build.sh orangepi5
```

The registry supplies defaults such as `BOARD`, `RELEASE`, and
`PREFER_DOCKER`. Shell environment variables win, so local overrides still
work:

```bash
BOARD=orangepi5-plus bash synapse_imager/build.sh orangepi5
OVERLAY_NAME=x86_64 bash synapse_imager/build.sh jetson
```

The same commands are available through `python3`:

```bash
python3 synapse_imager/platforms.py list
python3 synapse_imager/platforms.py matrix --pretty
python3 synapse_imager/platforms.py build orangepi5
python3 synapse_imager/platforms.py env orangepi5
python3 synapse_imager/platforms.py validate
```

### Adding a board

Add a target section to `platforms.ini`:

```ini
[target.orangepi5-ultra]
platform = armbian
name = Orange Pi 5 Ultra
env.BOARD = orangepi5-ultra
```

The board name must exist in Armbian's `config/boards/` directory. The builder
validates it before starting a long build. The workflow picks up the new target
on the next run. The same pattern covers Orange Pi, Radxa, Khadas, and Banana Pi
boards.

Raspberry Pi OS builds one image for every supported Pi model, so a new
Raspberry Pi usually needs no registry change. If a board needs a different OS
release or pi-gen ref, add a target with `env.RELEASE`, `env.PI_GEN_REF`, and a
distinct `artifact` name.

### Adding a platform

1. Create `synapse_imager/<platform>/build.sh` that produces an artifact in
   `OUT_DIR`.
2. Optionally create `synapse_imager/<platform>/setup.sh` for host
   dependencies. The release workflow runs it before the build.
3. Add a platform and at least one target to `platforms.ini`:

```ini
[platform.rockpi]
name = Rock Pi
builder = rockpi/build.sh
setup = rockpi/setup.sh
artifact = synapse-rockpi

[target.rockpi4]
platform = rockpi
name = Rock Pi 4
env.BOARD = rockpi4
```

Platform keys:

| Key | Meaning |
| --- | --- |
| `name` | Human-readable platform name (required) |
| `builder` | Build script relative to `synapse_imager/` (required) |
| `setup` | Optional host setup script relative to `synapse_imager/` |
| `runner` | GitHub Actions runner label (default `ubuntu-24.04`) |
| `timeout` | Job timeout in minutes (default `360`) |
| `free_disk` | Free runner disk space first (default `true`) |
| `artifact` | Artifact name (default `synapse-<target>`) |
| `env.<NAME>` | Environment default for every target on the platform |

Target keys are `platform`, `name`, `env.<NAME>`, and optional `runner`,
`timeout`, `free_disk`, and `artifact` overrides.

The registry is validated by `platforms.py validate`. It rejects unknown keys,
duplicate sections, missing builders, targets without a platform, and duplicate
artifact names.

## Release artifacts

| Artifact | Boards | Notes |
| --- | --- | --- |
| `synapse-raspberrypi-<version>-raspios-bookworm-arm64.img.xz` | Raspberry Pi 3/4/5, Zero 2 W (64-bit) | Built with [pi-gen](https://github.com/RPi-Distro/pi-gen) |
| `synapse-<board>-<version>-armbian-bookworm.img.xz` | Orange Pi 5 / 5 Plus / 5 Max, Radxa Rock 5B, and other Armbian boards | Built with [Armbian](https://github.com/armbian/build) |
| `synapse-jetson-overlay-<version>.tar.gz` | Jetson (JetPack/L4T) | Rootfs overlay; see [Linux overlay](#linux-overlay-jetson-and-x86_64) |
| `synapse-x86_64-overlay-<version>.tar.gz` | Beelink / Intel NUC and other x86_64 mini PCs | Rootfs overlay; see [Linux overlay](#linux-overlay-jetson-and-x86_64) |

### Default credentials

| Image | User | Password |
| --- | --- | --- |
| Raspberry Pi | `pi` | `synapse` |
| Armbian | `synapse` | `synapse` |

Linux overlays do not create a user. They provision the first regular user on
the existing system.

Change the password before putting a device on an untrusted network. The
installer's passwordless sudo rule is intentionally part of the image, so a
compromised runtime user already has root-equivalent access.

## Building locally

All builders accept a release wheel through `SYNAPSE_WHEEL`. When it is not
set, the builder uses the newest `dist/synapsefrc-*.whl`, so run `make build`
first (the wheel needs the built UI and simulator assets).

```bash
make build
```

Outputs are written to `dist/images/`.

### Raspberry Pi

```bash
SYNAPSE_WHEEL=dist/synapsefrc-*.whl \
  bash synapse_imager/build.sh raspberrypi
```

The builder uses pi-gen's Docker path by default. Set `USE_DOCKER=0` to run
pi-gen directly on an arm64 host. On a fresh host, run
`bash synapse_imager/raspberrypi/setup.sh` to install `qemu-user-static` and
`binfmt-support`.

Useful overrides:

```bash
PI_GEN_REF=2026-10-06-raspios-bookworm-arm64
RELEASE=bookworm
FIRST_USER_NAME=pi
FIRST_USER_PASS=synapse
TARGET_HOSTNAME=synapse
IMAGE_NAME=synapse-raspberrypi-custom
```

### Armbian single-board computers

```bash
SYNAPSE_WHEEL=dist/synapsefrc-*.whl \
  bash synapse_imager/build.sh orangepi5
```

The same builder supports every Armbian target in the registry, including
Orange Pi and Radxa boards:

```bash
bash synapse_imager/build.sh radxa-rock-5b
```

The wrapper clones the pinned Armbian release into `.image-build/armbian`,
installs the overlay in `userpatches/overlay`, and adds a
`userpatches/customize-image.sh` hook. The hook creates the runtime user,
enables password authentication for SSH, and runs the shared provisioner.

Useful overrides:

```bash
BOARD=orangepi5-plus
BRANCH=current
RELEASE=bookworm
ARMBIAN_REF=v26.5.1
TARGET_USER=synapse
TARGET_PASSWORD=synapse
PREFER_DOCKER=yes
IMAGE_NAME=synapse-orangepi5-plus-custom
```

Armbian builds are resource intensive (roughly 50 GB of disk and a long build
time). Run them on a machine with Docker and plenty of free space.

### Linux overlay (Jetson and x86_64)

```bash
SYNAPSE_WHEEL=dist/synapsefrc-*.whl \
  bash synapse_imager/build.sh jetson
bash synapse_imager/build.sh x86-64
```

The overlay build produces a tarball rather than a flashable image. NVIDIA's
JetPack/L4T BSP cannot be redistributed from CI, and x86_64 mini PCs normally
ship without an OS. Apply the overlay to a Debian/Ubuntu systemd rootfs before
flashing, or extract it on a running device:

```bash
sudo tar -xzf synapse-<target>-overlay-<version>.tar.gz -C /
sudo /opt/synapse-build/install.sh
```

For a mini PC, install Ubuntu Server 24.04 first and then extract the overlay.

The overlay installs a `synapse-firstboot.service` unit. On first boot it finds
the first regular user, provisions the runtime for that user, and disables
itself. First boot needs internet access to download Python dependencies, and
the rootfs must provide Python 3.11 or newer (JetPack 7 / Ubuntu 24.04 or
later).

## Release workflow

`.github/workflows/release_images.yml` runs on tags matching `v*` and on manual
dispatch.

1. `prepare` validates the registry, resolves the version, and turns every
   target in `platforms.ini` into a matrix entry.
2. `wheel` builds the release wheel from the tagged commit.
3. `images` builds every matrix target on its configured runner.
4. `release` attaches every artifact to the GitHub Release.

Manual dispatch builds the selected targets but does not publish a release. Use
it to smoke-test a branch or a new board:

```text
targets: orangepi5,radxa-rock-5b,x86-64
```

`targets` also accepts a platform id such as `armbian` or `overlay`. Use
`targets: all` (the default) to build everything.

The workflow uses the wheel built from the tag rather than a PyPI release, so
images always match the source tree that produced the tag.

## Tests

The image scripts are covered by `synapse_imager/tests/test_imager.py`:

- every shell script is parsed with `bash -n`,
- build scripts answer `--help`,
- the registry validates and every target appears in the workflow matrix,
- matrix filtering and build environment resolution work,
- the sample project has no credentials,
- the provisioner installs the runtime, sudoers rule, and systemd unit,
- the release workflow has the expected trigger and jobs.

Run them with the rest of the repository tests:

```bash
python -m pytest synapse_imager
```
