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
install -m 0644 files/synapsefrc.whl "${ROOTFS_DIR}/opt/synapse-build/synapsefrc.whl"
cp -a files/sample_project "${ROOTFS_DIR}/opt/synapse-build/sample_project"

on_chroot <<EOF
bash /opt/synapse-build/provision.sh \
  --wheel /opt/synapse-build/synapsefrc.whl \
  --project /opt/synapse-build/sample_project \
  --user "${FIRST_USER_NAME}" \
  --home "/home/${FIRST_USER_NAME}" \
  --skip-system-packages \
  --clean-apt \
  --cleanup
EOF
