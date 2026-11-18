# Synapse Jetson overlay

This directory contains the pieces installed by the Jetson overlay tarball.

NVIDIA does not permit redistributing a complete JetPack/L4T image, so the
release workflow publishes an overlay instead of a flashable image. Extract the
overlay over an L4T rootfs before flashing, or over `/` on a running Jetson.

On first boot, `synapse-firstboot.service` installs the runtime from the wheel
in `/opt/synapse-build` and places the sample project in the first regular
user's home directory. The service is disabled after a successful run.

First boot needs internet access because the runtime's dependencies are
downloaded from PyPI. The target rootfs must also provide Python 3.11 or newer
(JetPack 7 / Ubuntu 24.04 or later).

To provision immediately on a running device:

```bash
sudo /opt/synapse-build/install.sh
```
