#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Provision the Synapse runtime on a Debian/Ubuntu system. This script is
# installed as /usr/local/sbin/synapse-firstboot.sh by the overlay tarball and
# runs once on first boot. It can also be run manually after extracting the
# overlay onto a running device.

set -euo pipefail

STAGING="${SYNAPSE_STAGING:-/opt/synapse-build}"
MARKER="/var/lib/synapse/.provisioned"

if [[ -f "${MARKER}" ]]; then
  exit 0
fi

if [[ ! -d "${STAGING}" ]]; then
  echo "Synapse staging directory not found: ${STAGING}" >&2
  exit 1
fi

# JetPack and desktop installers create their user during setup. Pick the first
# regular user with a home directory instead of assuming a specific name.
USER_NAME="$(
  getent passwd |
    awk -F: '$3 >= 1000 && $3 < 60000 && $6 ~ /^\/home\// { print $1; exit }'
)"
if [[ -z "${USER_NAME}" ]]; then
  echo "No regular user found. Create a user before provisioning Synapse." >&2
  exit 1
fi

echo "Provisioning Synapse for ${USER_NAME}..."
# provision.sh discovers synapsefrc-*.whl next to itself. The staged wheel
# keeps its release filename so pip accepts it.
bash "${STAGING}/provision.sh" \
  --project "${STAGING}/sample_project" \
  --user "${USER_NAME}" \
  --clean-apt \
  --cleanup

install -d -m 0755 "$(dirname "${MARKER}")"
touch "${MARKER}"

systemctl disable synapse-firstboot.service >/dev/null 2>&1 || true
systemctl start synapse-runtime >/dev/null 2>&1 || true
