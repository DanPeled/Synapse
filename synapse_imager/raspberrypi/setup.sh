#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Install host dependencies for building Raspberry Pi images with pi-gen.

set -euo pipefail

case "${1:-}" in
  -h | --help)
    cat <<'EOF'
Usage: setup.sh

Install host dependencies for building Raspberry Pi images with pi-gen.
This installs qemu-user-static and binfmt-support so the arm64 rootfs can run
on an x86_64 host.
EOF
    exit 0
    ;;
  "")
    ;;
  *)
    echo "Unknown option: $1" >&2
    exit 2
    ;;
esac

if [[ "${EUID}" -eq 0 ]]; then
  apt-get update
  apt-get install -y qemu-user-static binfmt-support
else
  sudo apt-get update
  sudo apt-get install -y qemu-user-static binfmt-support
fi
