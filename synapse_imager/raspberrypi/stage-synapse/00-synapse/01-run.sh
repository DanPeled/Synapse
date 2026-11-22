#!/bin/bash -e
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Install the runtime from a release wheel and place the sample project in the
# first user's home directory. The build wrapper populates files/ with the
# wheel, the provisioning script, and the sample project.

install -d -m 0755 "${ROOTFS_DIR}/opt/synapse-build"
install -m 0755 files/provision.sh "${ROOTFS_DIR}/opt/synapse-build/provision.sh"
# The build wrapper stages the wheel under its release filename. Keep it that
# way: pip rejects a bare "synapsefrc.whl" as an invalid wheel name.
install -m 0644 files/synapsefrc-*.whl "${ROOTFS_DIR}/opt/synapse-build/"
cp -a files/sample_project "${ROOTFS_DIR}/opt/synapse-build/sample_project"

# Enable the USB device-mode controller. On Pi 4 / Zero 2 W the USB-C or
# micro-USB port can act as a gadget while the other ports stay in host mode.
# dr_mode=otg keeps normal host operation for boards that do not use gadget
# mode; the runtime service decides whether to configure the gadget at boot.
CONFIG_TXT="${ROOTFS_DIR}/boot/firmware/config.txt"
if [[ ! -f "${CONFIG_TXT}" ]]; then
  CONFIG_TXT="${ROOTFS_DIR}/boot/config.txt"
fi
if [[ -f "${CONFIG_TXT}" ]]; then
  grep -q '^dtoverlay=dwc2' "${CONFIG_TXT}" || echo 'dtoverlay=dwc2,dr_mode=otg' >>"${CONFIG_TXT}"
fi
CMDLINE_TXT="${ROOTFS_DIR}/boot/firmware/cmdline.txt"
if [[ ! -f "${CMDLINE_TXT}" ]]; then
  CMDLINE_TXT="${ROOTFS_DIR}/boot/cmdline.txt"
fi
if [[ -f "${CMDLINE_TXT}" ]]; then
  if ! grep -q 'modules-load=dwc2,libcomposite' "${CMDLINE_TXT}"; then
    sed -i '1 s/$/ modules-load=dwc2,libcomposite/' "${CMDLINE_TXT}"
  fi
fi

on_chroot <<EOF
bash /opt/synapse-build/provision.sh \
  --project /opt/synapse-build/sample_project \
  --user "${FIRST_USER_NAME}" \
  --home "/home/${FIRST_USER_NAME}" \
  --skip-system-packages \
  --clean-apt \
  --cleanup
EOF
