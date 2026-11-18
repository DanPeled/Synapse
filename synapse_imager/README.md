# Synapse device images

This directory builds OS images with the Synapse runtime preinstalled and a
sample project already deployed. Images are produced by the
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

## Release artifacts

| Artifact | Boards | Notes |
| --- | --- | --- |
| `synapse-raspberrypi-<version>-raspios-bookworm-arm64.img.xz` | Raspberry Pi 3/4/5, Zero 2 W (64-bit) | Built with [pi-gen](https://github.com/RPi-Distro/pi-gen) |
| `synapse-<board>-<version>-armbian-bookworm.img.xz` | Orange Pi 5, Orange Pi 5 Plus, and other Armbian boards | Built with [Armbian](https://github.com/armbian/build) |
| `synapse-jetson-overlay-<version>.tar.gz` | Jetson (JetPack/L4T) | Rootfs overlay; see [Jetson](#jetson) |

### Default credentials

| Image | User | Password |
| --- | --- | --- |
| Raspberry Pi | `pi` | `synapse` |
| Orange Pi | `synapse` | `synapse` |

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
  bash synapse_imager/raspberrypi/build.sh
```

The builder uses pi-gen's Docker path by default. Set `USE_DOCKER=0` to run
pi-gen directly on an arm64 host.

Useful overrides:

```bash
PI_GEN_REF=2026-10-06-raspios-bookworm-arm64
RELEASE=bookworm
FIRST_USER_NAME=pi
FIRST_USER_PASS=synapse
TARGET_HOSTNAME=synapse
```

### Orange Pi

```bash
BOARD=orangepi5 \
PREFER_DOCKER=yes \
SYNAPSE_WHEEL=dist/synapsefrc-*.whl \
  bash synapse_imager/orangepi/build.sh
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
```

Armbian builds are resource intensive (roughly 50 GB of disk and a long build
time). Run them on a machine with Docker and plenty of free space.

### Jetson

```bash
SYNAPSE_WHEEL=dist/synapsefrc-*.whl \
  bash synapse_imager/jetson/build.sh
```

The Jetson build produces an overlay tarball rather than a flashable image.
NVIDIA's JetPack/L4T BSP cannot be redistributed from CI. Apply the overlay to
an L4T rootfs before flashing, or extract it on a running device:

```bash
sudo tar -xzf synapse-jetson-overlay-<version>.tar.gz -C /
sudo /opt/synapse-build/install.sh
```

The overlay installs a `synapse-firstboot.service` unit. On first boot it finds
the first regular user, provisions the runtime for that user, and disables
itself. First boot needs internet access to download Python dependencies, and
the rootfs must provide Python 3.11 or newer (JetPack 7 / Ubuntu 24.04 or
later).

## Release workflow

`.github/workflows/release_images.yml` runs on tags matching `v*` and on manual
dispatch.

1. `prepare` resolves the version and the Orange Pi board matrix.
2. `wheel` builds the release wheel from the tagged commit.
3. `raspberrypi`, `orangepi`, and `jetson` build their artifacts from that
   wheel.
4. `release` attaches every artifact to the GitHub Release.

Manual dispatch builds the images but does not publish a release. Use it to
smoke-test a branch.

The workflow uses the wheel built from the tag rather than a PyPI release, so
images always match the source tree that produced the tag.

## Adding a board

For a new Orange Pi board, add its Armbian board name to the matrix in
`.github/workflows/release_images.yml`:

```yaml
default: "orangepi5,orangepi5-plus,orangepizero3"
```

The board name must exist in Armbian's `config/boards/` directory. The builder
validates it before starting a long build.

For a new image family, add a directory under `synapse_imager/` with a
`build.sh` that produces an artifact in `OUT_DIR`, then add a job to the
release workflow.

## Tests

The image scripts are covered by `synapse_imager/tests/test_imager.py`:

- every shell script is parsed with `bash -n`,
- build scripts answer `--help`,
- the sample project has no credentials,
- the provisioner installs the runtime, sudoers rule, and systemd unit,
- the release workflow has the expected trigger and jobs.

Run them with the rest of the repository tests:

```bash
python -m pytest synapse_imager
```
