#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Build a Raspberry Pi OS image with the Synapse runtime preinstalled.
#
# The image is built with pi-gen. On x86_64 hosts the Docker build path is used
# so the arm64 rootfs can run through QEMU.
#
# Environment:
#   SYNAPSE_WHEEL     Release wheel to install. The newest dist/*.whl is used
#                     when omitted.
#   SYNAPSE_VERSION   Image version. Defaults to SYNAPSE_VERSION in the source.
#   OUT_DIR           Output directory. Defaults to <repo>/dist/images.
#   PI_GEN_REF        pi-gen tag or commit. Defaults to the bookworm arm64 tag.
#   PI_GEN_DIR        pi-gen checkout. Defaults to <repo>/.image-build/pi-gen.
#   RELEASE           Debian release. Defaults to bookworm.
#   FIRST_USER_NAME   Default user. Defaults to pi.
#   FIRST_USER_PASS   Default password. Defaults to synapse.
#   TARGET_HOSTNAME   Default hostname. Defaults to synapse.
#   WPA_COUNTRY       Wi-Fi country code. Defaults to US.
#   USE_DOCKER        Set to 0 to run pi-gen directly instead of in Docker.
#   IMAGE_NAME        Output image name. Defaults to
#                     synapse-raspberrypi-<version>-raspios-<release>-arm64.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGER_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${IMAGER_DIR}/.." && pwd)"

# shellcheck source=../common/helpers.sh
source "${IMAGER_DIR}/common/helpers.sh"

usage() {
  cat <<'EOF'
Usage: build.sh [options]

Build a Raspberry Pi OS image with the Synapse runtime preinstalled.

Environment:
  SYNAPSE_WHEEL     Release wheel to install. The newest dist/*.whl is used
                    when omitted.
  SYNAPSE_VERSION   Image version. Defaults to SYNAPSE_VERSION in the source.
  OUT_DIR           Output directory. Defaults to <repo>/dist/images.
  PI_GEN_REF        pi-gen tag or commit. Defaults to the bookworm arm64 tag.
  PI_GEN_DIR        pi-gen checkout. Defaults to <repo>/.image-build/pi-gen.
  RELEASE           Debian release. Defaults to bookworm.
  FIRST_USER_NAME   Default user. Defaults to pi.
  FIRST_USER_PASS   Default password. Defaults to synapse.
  TARGET_HOSTNAME   Default hostname. Defaults to synapse.
  WPA_COUNTRY       Wi-Fi country code. Defaults to US.
  USE_DOCKER        Set to 0 to run pi-gen directly instead of in Docker.
  IMAGE_NAME        Output image name. Defaults to
                    synapse-raspberrypi-<version>-raspios-<release>-arm64.
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

RELEASE="${RELEASE:-bookworm}"
PI_GEN_REF="${PI_GEN_REF:-2026-10-06-raspios-bookworm-arm64}"
PI_GEN_DIR="${PI_GEN_DIR:-${REPO_ROOT}/.image-build/pi-gen}"
OUT_DIR="${OUT_DIR:-${REPO_ROOT}/dist/images}"
FIRST_USER_NAME="${FIRST_USER_NAME:-pi}"
FIRST_USER_PASS="${FIRST_USER_PASS:-synapse}"
TARGET_HOSTNAME="${TARGET_HOSTNAME:-synapse}"
WPA_COUNTRY="${WPA_COUNTRY:-US}"
USE_DOCKER="${USE_DOCKER:-1}"

VERSION="${SYNAPSE_VERSION:-$(synapse_version "${REPO_ROOT}")}"
IMAGE_NAME="${IMAGE_NAME:-synapse-raspberrypi-${VERSION}-raspios-${RELEASE}-arm64}"
WHEEL="$(ensure_synapse_wheel "${REPO_ROOT}")"

checkout_ref \
  https://github.com/RPi-Distro/pi-gen.git "${PI_GEN_REF}" "${PI_GEN_DIR}"

STAGE_SRC="${SCRIPT_DIR}/stage-synapse"
STAGE_DST="${PI_GEN_DIR}/stage-synapse"

rm -rf "${STAGE_DST}"
cp -a "${STAGE_SRC}" "${STAGE_DST}"

install -m 0755 "${IMAGER_DIR}/common/provision.sh" \
  "${STAGE_DST}/00-synapse/files/provision.sh"
install -m 0644 "${WHEEL}" "${STAGE_DST}/00-synapse/files/synapsefrc.whl"
rm -rf "${STAGE_DST}/00-synapse/files/sample_project"
cp -a "${IMAGER_DIR}/sample_project" \
  "${STAGE_DST}/00-synapse/files/sample_project"

# stage2 also exports an image. Only the Synapse stage should produce an
# artifact, so skip the intermediate lite image.
touch "${PI_GEN_DIR}/stage2/SKIP_IMAGES"

CONFIG_FILE="${PI_GEN_DIR}/config.synapse"
cat >"${CONFIG_FILE}" <<EOF
IMG_NAME="${IMAGE_NAME}"
RELEASE="${RELEASE}"
DEPLOY_COMPRESSION="xz"
COMPRESSION_LEVEL="6"
LOCALE_DEFAULT="en_US.UTF-8"
KEYBOARD_KEYMAP="us"
KEYBOARD_LAYOUT="English (US)"
TIMEZONE_DEFAULT="Etc/UTC"
TARGET_HOSTNAME="${TARGET_HOSTNAME}"
FIRST_USER_NAME="${FIRST_USER_NAME}"
FIRST_USER_PASS="${FIRST_USER_PASS}"
DISABLE_FIRST_BOOT_USER_RENAME=1
ENABLE_SSH=1
PUBKEY_ONLY_SSH=0
WPA_COUNTRY="${WPA_COUNTRY}"
STAGE_LIST="stage0 stage1 stage2 stage-synapse"
PI_GEN_RELEASE="Synapse"
EOF

echo "Building Raspberry Pi image for Synapse ${VERSION}..."
cd "${PI_GEN_DIR}"
if [[ "${USE_DOCKER}" == "1" ]]; then
  ./build-docker.sh -c "${CONFIG_FILE}"
else
  if [[ "${EUID}" -ne 0 ]]; then
    sudo ./build.sh -c "${CONFIG_FILE}"
  else
    ./build.sh -c "${CONFIG_FILE}"
  fi
fi

shopt -s nullglob
images=(
  "${PI_GEN_DIR}"/deploy/*.img.xz
  "${PI_GEN_DIR}"/deploy/*.img.gz
  "${PI_GEN_DIR}"/deploy/*.img.zip
  "${PI_GEN_DIR}"/deploy/*.img
)
shopt -u nullglob

if (( ${#images[@]} == 0 )); then
  echo "pi-gen did not produce an image in ${PI_GEN_DIR}/deploy" >&2
  exit 1
fi

image=""
for candidate in "${images[@]}"; do
  if [[ "$(basename "${candidate}")" == *synapse* ]]; then
    image="${candidate}"
    break
  fi
done
image="${image:-${images[0]}}"

case "${image}" in
  *.img.xz) suffix=".img.xz" ;;
  *.img.gz) suffix=".img.gz" ;;
  *.img.zip) suffix=".img.zip" ;;
  *.img) suffix=".img" ;;
  *) suffix=".${image##*.}" ;;
esac

mkdir -p "${OUT_DIR}"
destination="${OUT_DIR}/${IMAGE_NAME}${suffix}"
cp "${image}" "${destination}"

echo "Created ${destination}"
