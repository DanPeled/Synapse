#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Armbian customize-image.sh hook.
#
# Armbian runs this script inside the target rootfs and bind-mounts the
# userpatches/overlay directory at /tmp/overlay. The build wrapper puts the
# wheel, provisioning script, sample project, and image.env there.

set -euo pipefail

RELEASE="${1:-bookworm}"
LINUXFAMILY="${2:-}"
BOARD="${3:-}"
BUILD_DESKTOP="${4:-no}"

STAGING="/tmp/overlay/opt/synapse-build"
if [[ ! -d "${STAGING}" ]]; then
  echo "Synapse staging directory is missing: ${STAGING}" >&2
  exit 1
fi

# shellcheck source=/dev/null
source "${STAGING}/image.env"

export DEBIAN_FRONTEND=noninteractive

if ! id "${TARGET_USER}" >/dev/null 2>&1; then
  getent group sudo >/dev/null 2>&1 || groupadd sudo
  useradd --create-home --shell /bin/bash --groups sudo "${TARGET_USER}"
fi
echo "${TARGET_USER}:${TARGET_PASSWORD}" | chpasswd

# The installer connects over SSH with a password, so password authentication
# must stay available for the runtime user.
systemctl enable ssh >/dev/null 2>&1 || true
if [[ -f /etc/ssh/sshd_config ]]; then
  sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config
  sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
fi

# Armbian asks for a new root password and a user on first login. The image
# already has a runtime user, so skip that prompt and lock the root account.
rm -f /root/.not_logged_in_yet
passwd -l root >/dev/null 2>&1 || true

bash "${STAGING}/provision.sh" \
  --wheel "${STAGING}/synapsefrc.whl" \
  --project "${STAGING}/sample_project" \
  --user "${TARGET_USER}" \
  --clean-apt

echo "Synapse customization complete for ${BOARD} (${RELEASE}, ${LINUXFAMILY}, desktop=${BUILD_DESKTOP})"
