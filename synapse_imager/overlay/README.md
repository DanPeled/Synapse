# Synapse Linux overlay

This directory contains the pieces installed by the Linux overlay tarball. The
overlay targets Debian/Ubuntu systems with systemd and Python 3.11 or newer,
including:

- Jetson devices running JetPack 7 / Ubuntu 24.04 or later,
- x86_64 mini PCs such as the Beelink Mini S12/EQ12 and Intel NUC,
- other Debian/Ubuntu coprocessors.

NVIDIA does not permit redistributing a complete JetPack/L4T image, so Jetson
gets an overlay instead of a flashable image. x86_64 mini PCs normally ship
without an OS, so install Ubuntu Server 24.04 first and then apply the overlay.

On first boot, `synapse-firstboot.service` installs the runtime from the wheel
in `/opt/synapse-build` and places the sample project in the first regular
user's home directory. The service is disabled after a successful run.

First boot needs internet access because the runtime's dependencies are
downloaded from PyPI. The target system must also provide Python 3.11 or newer.

Apply the overlay over an L4T rootfs before flashing, or extract it on a
running device:

```bash
sudo tar -xzf synapse-<target>-overlay-<version>.tar.gz -C /
sudo /opt/synapse-build/install.sh
```

To provision immediately on a running device, run the install script as shown
above. It is equivalent to letting the first-boot service run on the next boot.
