#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Configure the USB gadget for direct computer connections. Called by the
# synapse-usb-gadget systemd service. It uses the Synapse Python module so all
# board-specific discovery (UDC, function, interface, link-local address) is
# handled in one tested place.

set -euo pipefail

VENV_PYTHON="${SYNAPSE_VENV_PYTHON:-/opt/synapse/venv/bin/python}"
if [[ ! -x "${VENV_PYTHON}" ]]; then
  # Fall back to the user's virtualenv layout used by provision.sh.
  VENV_PYTHON="$(getent passwd synapse 2>/dev/null | cut -d: -f6)/.venv/bin/python"
fi

ACTION="${1:-start}"

start() {
  "${VENV_PYTHON}" - <<'PY'
import sys
from pathlib import Path

from synapse.hardware.usb_gadget import UsbGadgetError, UsbGadgetManager

manager = UsbGadgetManager()
if not manager.isAvailable():
    print("USB gadget mode is not available on this board; skipping.")
    sys.exit(0)
try:
    config = manager.start()
    info = Path("/run/synapse-usb-gadget.txt")
    info.write_text(
        f"{config.advertisedAddress}\n{config.interface}\n{config.serial}\n",
        encoding="utf-8",
    )
    print(f"USB gadget ready at {config.advertisedAddress} on {config.interface}")
except UsbGadgetError as e:
    print(f"USB gadget configuration failed: {e}", file=sys.stderr)
    sys.exit(1)
PY
}

stop() {
  "${VENV_PYTHON}" - <<'PY'
from synapse.hardware.usb_gadget import UsbGadgetManager

UsbGadgetManager().stop()
PY
}

case "${ACTION}" in
  start) start ;;
  stop) stop ;;
  *)
    echo "Usage: $0 {start|stop}" >&2
    exit 2
    ;;
esac
