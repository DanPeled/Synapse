#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Install the Synapse runtime and a sample project into a Debian-based rootfs.
#
# The script is intentionally usable in three places:
#
#   * inside an image build chroot (pi-gen, Armbian),
#   * on a running device (the Jetson overlay), and
#   * by a developer who wants the same layout as a release image.
#
# It always operates on an explicit user and home directory so it never relies
# on the caller's $HOME.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

USER_NAME="${SYNAPSE_USER:-pi}"
USER_HOME=""
WHEEL=""
PROJECT=""
VENV_DIR=""
APP_DIR=""
SERVICE_NAME="${SYNAPSE_SERVICE_NAME:-synapse-runtime}"
EXTRAS="${SYNAPSE_EXTRAS:-}"
SKIP_SYSTEM_PACKAGES=0
CLEAN_APT=0
CLEANUP=0
USB_GADGET=-1  # -1 = auto-detect from staged assets

DEFAULT_PACKAGES=(
  python3
  python3-venv
  python3-pip
  unzip
  isc-dhcp-client
  libgl1
  libglib2.0-0
  libgomp1
  libsm6
  libxext6
  libxrender1
  libopencv-dev
  v4l-utils
  mtools
)

usage() {
  cat <<'EOF'
Usage: provision.sh [options]

Install the Synapse runtime and a sample project for one device user.

Options:
  --wheel PATH             Synapse wheel to install. Defaults to the first
                           synapsefrc-*.whl next to this script.
  --project PATH           Project to install (default: ./sample_project).
  --user NAME              Device user that owns the runtime (default: pi).
  --home PATH              Home directory for --user (default: /etc/passwd).
  --venv PATH              Virtualenv path (default: <home>/.venv).
  --app-dir PATH           Project path on the device (default: <home>/Synapse).
  --service-name NAME      systemd unit name (default: synapse-runtime).
  --extras EXTRAS          Comma-separated pip extras, for example "yolo".
  --usb-gadget             Force-install USB gadget mode (default: auto-detect).
  --no-usb-gadget          Do not install USB gadget mode.
  --skip-system-packages   Do not install OS packages.
  --clean-apt              Remove apt lists and caches after provisioning.
  --cleanup                Remove this staging directory when finished.
  -h, --help               Show this help.

Environment:
  SYNAPSE_USER             Default for --user.
  SYNAPSE_EXTRAS           Default for --extras.
  SYNAPSE_SERVICE_NAME     Default for --service-name.
  SYNAPSE_PYTHON           Python 3.11+ interpreter (default: python3).
  SYNAPSE_EXTRA_PACKAGES   Extra OS packages, separated by spaces.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --wheel)
      WHEEL="${2:?--wheel requires a value}"
      shift 2
      ;;
    --project)
      PROJECT="${2:?--project requires a value}"
      shift 2
      ;;
    --user)
      USER_NAME="${2:?--user requires a value}"
      shift 2
      ;;
    --home)
      USER_HOME="${2:?--home requires a value}"
      shift 2
      ;;
    --venv)
      VENV_DIR="${2:?--venv requires a value}"
      shift 2
      ;;
    --app-dir)
      APP_DIR="${2:?--app-dir requires a value}"
      shift 2
      ;;
    --service-name)
      SERVICE_NAME="${2:?--service-name requires a value}"
      shift 2
      ;;
    --extras)
      EXTRAS="${2:?--extras requires a value}"
      shift 2
      ;;
    --usb-gadget)
      USB_GADGET=1
      shift
      ;;
    --no-usb-gadget)
      USB_GADGET=0
      shift
      ;;
    --skip-system-packages)
      SKIP_SYSTEM_PACKAGES=1
      shift
      ;;
    --clean-apt)
      CLEAN_APT=1
      shift
      ;;
    --cleanup)
      CLEANUP=1
      shift
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ "${EUID}" -ne 0 ]]; then
  echo "provision.sh must run as root" >&2
  exit 1
fi

if [[ -z "${WHEEL}" ]]; then
  shopt -s nullglob
  wheels=("${SCRIPT_DIR}"/synapsefrc-*.whl)
  shopt -u nullglob
  if (( ${#wheels[@]} == 0 )); then
    echo "No --wheel given and no synapsefrc-*.whl found in ${SCRIPT_DIR}" >&2
    exit 1
  fi
  WHEEL="${wheels[0]}"
fi

if [[ ! -f "${WHEEL}" ]]; then
  echo "Wheel not found: ${WHEEL}" >&2
  exit 1
fi
WHEEL="$(cd "$(dirname "${WHEEL}")" && pwd)/$(basename "${WHEEL}")"

# pip validates wheel filenames strictly. A bare "synapsefrc.whl" looks like a
# wheel to the staging scripts but fails in pip with "Invalid wheel filename
# (wrong number of parts)". Fail early here with an actionable message.
wheel_name="$(basename "${WHEEL}")"
wheel_stem="${wheel_name%.whl}"
IFS='-' read -r -a wheel_parts <<<"${wheel_stem}"
if [[ "${wheel_name}" != *.whl ]] || (( ${#wheel_parts[@]} < 5 )); then
  echo "Invalid wheel filename: ${wheel_name}" >&2
  echo "Expected <distribution>-<version>-<python>-<abi>-<platform>.whl" >&2
  exit 1
fi

PROJECT="${PROJECT:-${SCRIPT_DIR}/sample_project}"
if [[ ! -d "${PROJECT}" ]]; then
  echo "Project not found: ${PROJECT}" >&2
  exit 1
fi
PROJECT="$(cd "${PROJECT}" && pwd)"

if ! id "${USER_NAME}" >/dev/null 2>&1; then
  echo "Creating user ${USER_NAME}"
  useradd --create-home --shell /bin/bash "${USER_NAME}"
fi

USER_GROUP="$(id -gn "${USER_NAME}")"

if [[ -z "${USER_HOME}" ]]; then
  USER_HOME="$(getent passwd "${USER_NAME}" | cut -d: -f6)"
fi
USER_HOME="${USER_HOME:-/home/${USER_NAME}}"

VENV_DIR="${VENV_DIR:-${USER_HOME}/.venv}"
APP_DIR="${APP_DIR:-${USER_HOME}/Synapse}"

PYTHON_BIN="${SYNAPSE_PYTHON:-python3}"
if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "Python interpreter not found: ${PYTHON_BIN}" >&2
  exit 1
fi
if ! "${PYTHON_BIN}" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 11) else 1)'; then
  echo "Synapse requires Python 3.11 or newer; found $("${PYTHON_BIN}" --version 2>&1)" >&2
  echo "Set SYNAPSE_PYTHON to a suitable interpreter if one is installed elsewhere." >&2
  exit 1
fi

as_user() {
  # Set HOME explicitly: runuser does not always inherit the target user's
  # environment, and pip would otherwise try to write to /root/.cache.
  runuser -u "${USER_NAME}" -- \
    env HOME="${USER_HOME}" USER="${USER_NAME}" LOGNAME="${USER_NAME}" "$@"
}

# ---------------------------------------------------------------------------
# OS packages
# ---------------------------------------------------------------------------

if [[ "${SKIP_SYSTEM_PACKAGES}" -eq 0 ]]; then
  if command -v apt-get >/dev/null 2>&1; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y --no-install-recommends "${DEFAULT_PACKAGES[@]}"

    if [[ -n "${SYNAPSE_EXTRA_PACKAGES:-}" ]]; then
      # shellcheck disable=SC2206
      extra_packages=(${SYNAPSE_EXTRA_PACKAGES})
      apt-get install -y --no-install-recommends "${extra_packages[@]}"
    fi
  else
    echo "apt-get not found; skipping system package installation" >&2
  fi
fi

# ---------------------------------------------------------------------------
# Python virtualenv + runtime
# ---------------------------------------------------------------------------

mkdir -p "$(dirname "${VENV_DIR}")"
chown "${USER_NAME}:${USER_GROUP}" "$(dirname "${VENV_DIR}")"

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
  as_user "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

as_user "${VENV_DIR}/bin/python" -m pip install --no-cache-dir --upgrade pip setuptools wheel

WHEEL_SPEC="${WHEEL}"
if [[ -n "${EXTRAS}" ]]; then
  WHEEL_SPEC="${WHEEL}[${EXTRAS}]"
fi

as_user "${VENV_DIR}/bin/python" -m pip install --no-cache-dir "${WHEEL_SPEC}"

# ---------------------------------------------------------------------------
# Sample project
# ---------------------------------------------------------------------------

mkdir -p "${APP_DIR}"
if [[ ! -f "${APP_DIR}/main.py" ]]; then
  cp -a "${PROJECT}/." "${APP_DIR}/"
fi

mkdir -p \
  "${APP_DIR}/config" \
  "${APP_DIR}/pipelines" \
  "${APP_DIR}/deploy" \
  "${APP_DIR}/records" \
  "${APP_DIR}/logs"

chown -R "${USER_NAME}:${USER_GROUP}" "${APP_DIR}"

# ---------------------------------------------------------------------------
# Passwordless sudo for the installer
# ---------------------------------------------------------------------------

SUDOERS_FILE="/etc/sudoers.d/90-synapse-${USER_NAME}"
printf '%s ALL=(ALL) NOPASSWD:ALL\n' "${USER_NAME}" >"${SUDOERS_FILE}"
chmod 0440 "${SUDOERS_FILE}"
if command -v visudo >/dev/null 2>&1; then
  visudo -cf "${SUDOERS_FILE}" >/dev/null
fi

# ---------------------------------------------------------------------------
# systemd service
# ---------------------------------------------------------------------------

SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
cat >"${SERVICE_FILE}" <<EOF
[Unit]
Description=Synapse Runtime
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${USER_NAME}
WorkingDirectory=${APP_DIR}
ExecStart=${VENV_DIR}/bin/python ${APP_DIR}/main.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF
chmod 0644 "${SERVICE_FILE}"

if command -v systemctl >/dev/null 2>&1; then
  systemctl daemon-reload >/dev/null 2>&1 || true
  systemctl enable "${SERVICE_NAME}" >/dev/null 2>&1 || true
fi

# `systemctl enable` can fail in a chroot. Creating the symlink directly keeps
# the image bootable either way.
WANTS_DIR="/etc/systemd/system/multi-user.target.wants"
mkdir -p "${WANTS_DIR}"
ln -sfn "${SERVICE_FILE}" "${WANTS_DIR}/${SERVICE_NAME}.service"

# ---------------------------------------------------------------------------
# USB gadget (direct USB/Ethernet connection)
# ---------------------------------------------------------------------------

GADGET_SRC="${SCRIPT_DIR}/usb_gadget"
if [[ "${USB_GADGET}" -eq -1 ]]; then
  USB_GADGET=0
  [[ -d "${GADGET_SRC}" ]] && USB_GADGET=1
fi

if [[ "${USB_GADGET}" -eq 1 ]]; then
  if [[ -d "${GADGET_SRC}" ]]; then
    install -d -m 0755 /usr/local/sbin /var/lib/synapse/usb_gadget
    install -m 0755 "${GADGET_SRC}/synapse-usb-gadget.sh" /usr/local/sbin/synapse-usb-gadget.sh
    install -m 0644 "${GADGET_SRC}/synapse-usb-gadget.service" \
      /etc/systemd/system/synapse-usb-gadget.service
    sed -i "s|/opt/synapse/venv/bin/python|${VENV_DIR}/bin/python|g" \
      /usr/local/sbin/synapse-usb-gadget.sh
    if command -v systemctl >/dev/null 2>&1; then
      systemctl daemon-reload >/dev/null 2>&1 || true
      systemctl enable synapse-usb-gadget >/dev/null 2>&1 || true
    fi
    ln -sfn /etc/systemd/system/synapse-usb-gadget.service \
      "${WANTS_DIR}/synapse-usb-gadget.service"
    echo "USB gadget mode installed"
  else
    echo "USB gadget assets not found in ${GADGET_SRC}" >&2
  fi
fi

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

if [[ "${CLEAN_APT}" -eq 1 ]]; then
  if command -v apt-get >/dev/null 2>&1; then
    apt-get clean
    rm -rf /var/lib/apt/lists/*
  fi
fi

if [[ "${CLEANUP}" -eq 1 && "${SCRIPT_DIR}" == "/opt/synapse-build" ]]; then
  rm -rf "${SCRIPT_DIR}"
fi

echo "Synapse runtime installed"
echo "  user:    ${USER_NAME}"
echo "  venv:    ${VENV_DIR}"
echo "  project: ${APP_DIR}"
echo "  service: ${SERVICE_NAME}"
