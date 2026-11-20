#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Convenience wrapper around synapse_imager/platforms.py.
#
#   bash synapse_imager/build.sh                 # list the registry
#   bash synapse_imager/build.sh list            # list the registry
#   bash synapse_imager/build.sh orangepi5       # build one target
#   bash synapse_imager/build.sh build orangepi5 # same thing
#   bash synapse_imager/build.sh matrix          # workflow matrix as JSON

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if (( $# == 0 )); then
  exec python3 "${SCRIPT_DIR}/platforms.py" --help
fi

case "$1" in
  -h | --help | list | matrix | build | env | validate)
    exec python3 "${SCRIPT_DIR}/platforms.py" "$@"
    ;;
  *)
    exec python3 "${SCRIPT_DIR}/platforms.py" build "$@"
    ;;
esac
