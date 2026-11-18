#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Build a Jetson overlay tarball containing the Synapse runtime and sample
# project. The overlay is meant to be applied to a JetPack/L4T rootfs before
# flashing, or extracted on a running Jetson.
#
# A complete flashable Jetson image is not built here because the NVIDIA BSP
# cannot be redistributed from CI.
#
# Environment:
#   SYNAPSE_WHEEL     Release wheel to install. The newest dist/*.whl is used
#                     when omitted.
#   SYNAPSE_VERSION   Overlay version. Defaults to SYNAPSE_VERSION in the
#                     source.
#   OUT_DIR           Output directory. Defaults to <repo>/dist/images.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGER_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${IMAGER_DIR}/.." && pwd)"

# shellcheck source=../common/helpers.sh
source "${IMAGER_DIR}/common/helpers.sh"

usage() {
  cat <<'EOF'
Usage: build.sh [options]

Build a Jetson overlay tarball containing the Synapse runtime and sample
project. Apply it to a JetPack/L4T rootfs before flashing, or extract it on a
running Jetson.

Environment:
  SYNAPSE_WHEEL     Release wheel to install. The newest dist/*.whl is used
                    when omitted.
  SYNAPSE_VERSION   Overlay version. Defaults to SYNAPSE_VERSION in the source.
  OUT_DIR           Output directory. Defaults to <repo>/dist/images.
EOF
}

case "${1:-}" in
  -h | --help)
    usage
    exit 0
    ;;
  "")
    ;;
  *)
    echo "Unknown option: $1" >&2
    usage >&2
    exit 2
    ;;
esac

OUT_DIR="${OUT_DIR:-${REPO_ROOT}/dist/images}"
VERSION="${SYNAPSE_VERSION:-$(synapse_version "${REPO_ROOT}")}"
WHEEL="$(ensure_synapse_wheel "${REPO_ROOT}")"

STAGE="${REPO_ROOT}/.image-build/jetson-overlay"
rm -rf "${STAGE}"

mkdir -p \
  "${STAGE}/opt/synapse-build" \
  "${STAGE}/usr/local/sbin" \
  "${STAGE}/etc/systemd/system/multi-user.target.wants"

install -m 0755 "${IMAGER_DIR}/common/provision.sh" \
  "${STAGE}/opt/synapse-build/provision.sh"
install -m 0644 "${WHEEL}" "${STAGE}/opt/synapse-build/synapsefrc.whl"
cp -a "${IMAGER_DIR}/sample_project" "${STAGE}/opt/synapse-build/sample_project"

install -m 0755 "${SCRIPT_DIR}/firstboot.sh" \
  "${STAGE}/usr/local/sbin/synapse-firstboot.sh"
install -m 0755 "${SCRIPT_DIR}/install.sh" \
  "${STAGE}/opt/synapse-build/install.sh"
install -m 0644 "${SCRIPT_DIR}/synapse-firstboot.service" \
  "${STAGE}/etc/systemd/system/synapse-firstboot.service"
install -m 0644 "${SCRIPT_DIR}/README.md" \
  "${STAGE}/opt/synapse-build/README.md"

ln -sfn /etc/systemd/system/synapse-firstboot.service \
  "${STAGE}/etc/systemd/system/multi-user.target.wants/synapse-firstboot.service"

mkdir -p "${OUT_DIR}"
destination="${OUT_DIR}/synapse-jetson-overlay-${VERSION}.tar.gz"

tar --owner=0 --group=0 --numeric-owner \
  -C "${STAGE}" -czf "${destination}" .

echo "Created ${destination}"
