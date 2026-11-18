#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Build an Armbian image for an Orange Pi with the Synapse runtime
# preinstalled. The Armbian build framework performs the actual kernel,
# bootloader, and rootfs work; this wrapper only supplies an overlay and the
# customize-image.sh hook.
#
# Environment:
#   BOARD             Armbian board name. Defaults to orangepi5.
#   BRANCH            Armbian kernel branch. Defaults to current.
#   RELEASE           Debian release. Defaults to bookworm.
#   SYNAPSE_WHEEL     Release wheel to install. The newest dist/*.whl is used
#                     when omitted.
#   SYNAPSE_VERSION   Image version. Defaults to SYNAPSE_VERSION in the source.
#   OUT_DIR           Output directory. Defaults to <repo>/dist/images.
#   ARMBIAN_REF       Armbian tag or commit. Defaults to v26.5.1.
#   ARMBIAN_DIR       Armbian checkout. Defaults to <repo>/.image-build/armbian.
#   TARGET_USER       Runtime user. Defaults to synapse.
#   TARGET_PASSWORD   Runtime user password. Defaults to synapse.
#   PREFER_DOCKER     Set to yes to run the Armbian build in Docker.
#   COMPRESS_OUTPUTIMAGE  Armbian compression list. Defaults to sha,img,xz.
#   IMAGE_NAME        Output image name. Defaults to
#                     synapse-<board>-<version>-armbian-<release>.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGER_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${IMAGER_DIR}/.." && pwd)"

# shellcheck source=../common/helpers.sh
source "${IMAGER_DIR}/common/helpers.sh"

usage() {
  cat <<'EOF'
Usage: build.sh [options]

Build an Armbian image for an Orange Pi with the Synapse runtime preinstalled.

Environment:
  BOARD             Armbian board name. Defaults to orangepi5.
  BRANCH            Armbian kernel branch. Defaults to current.
  RELEASE           Debian release. Defaults to bookworm.
  SYNAPSE_WHEEL     Release wheel to install. The newest dist/*.whl is used
                    when omitted.
  SYNAPSE_VERSION   Image version. Defaults to SYNAPSE_VERSION in the source.
  OUT_DIR           Output directory. Defaults to <repo>/dist/images.
  ARMBIAN_REF       Armbian tag or commit. Defaults to v26.5.1.
  ARMBIAN_DIR       Armbian checkout. Defaults to <repo>/.image-build/armbian.
  TARGET_USER       Runtime user. Defaults to synapse.
  TARGET_PASSWORD   Runtime user password. Defaults to synapse.
  PREFER_DOCKER     Set to yes to run the Armbian build in Docker.
  COMPRESS_OUTPUTIMAGE  Armbian compression list. Defaults to sha,img,xz.
  IMAGE_NAME        Output image name. Defaults to
                    synapse-<board>-<version>-armbian-<release>.
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

BOARD="${BOARD:-orangepi5}"
BRANCH="${BRANCH:-current}"
RELEASE="${RELEASE:-bookworm}"
ARMBIAN_REF="${ARMBIAN_REF:-v26.5.1}"
ARMBIAN_DIR="${ARMBIAN_DIR:-${REPO_ROOT}/.image-build/armbian}"
OUT_DIR="${OUT_DIR:-${REPO_ROOT}/dist/images}"
TARGET_USER="${TARGET_USER:-synapse}"
TARGET_PASSWORD="${TARGET_PASSWORD:-synapse}"
PREFER_DOCKER="${PREFER_DOCKER:-no}"
COMPRESS_OUTPUTIMAGE="${COMPRESS_OUTPUTIMAGE:-sha,img,xz}"

VERSION="${SYNAPSE_VERSION:-$(synapse_version "${REPO_ROOT}")}"
IMAGE_NAME="${IMAGE_NAME:-synapse-${BOARD}-${VERSION}-armbian-${RELEASE}}"
WHEEL="$(ensure_synapse_wheel "${REPO_ROOT}")"

checkout_ref \
  https://github.com/armbian/build.git "${ARMBIAN_REF}" "${ARMBIAN_DIR}"

if [[ ! -f "${ARMBIAN_DIR}/config/boards/${BOARD}.conf" && ! -f "${ARMBIAN_DIR}/config/boards/${BOARD}.csc" ]]; then
  echo "Unknown Armbian board: ${BOARD}" >&2
  echo "Available Orange Pi boards:" >&2
  find "${ARMBIAN_DIR}/config/boards" -maxdepth 1 -type f -name 'orangepi*' \
    -printf '  %f\n' | sort >&2
  exit 1
fi

USERPATCHES="${ARMBIAN_DIR}/userpatches"
OVERLAY="${USERPATCHES}/overlay/opt/synapse-build"

rm -rf "${USERPATCHES}"
mkdir -p "${OVERLAY}"

install -m 0755 "${IMAGER_DIR}/common/provision.sh" "${OVERLAY}/provision.sh"
install -m 0644 "${WHEEL}" "${OVERLAY}/synapsefrc.whl"
cp -a "${IMAGER_DIR}/sample_project" "${OVERLAY}/sample_project"
install -m 0755 "${SCRIPT_DIR}/customize-image.sh" "${USERPATCHES}/customize-image.sh"

{
  printf 'TARGET_USER=%q\n' "${TARGET_USER}"
  printf 'TARGET_PASSWORD=%q\n' "${TARGET_PASSWORD}"
} >"${OVERLAY}/image.env"

echo "Building Armbian image for ${BOARD} (${RELEASE}, ${BRANCH}) with Synapse ${VERSION}..."
(
  cd "${ARMBIAN_DIR}"
  ./compile.sh build \
    BOARD="${BOARD}" \
    BRANCH="${BRANCH}" \
    RELEASE="${RELEASE}" \
    BUILD_DESKTOP=no \
    BUILD_MINIMAL=no \
    KERNEL_CONFIGURE=no \
    COMPRESS_OUTPUTIMAGE="${COMPRESS_OUTPUTIMAGE}" \
    PREFER_DOCKER="${PREFER_DOCKER}"
)

shopt -s nullglob
images=(
  "${ARMBIAN_DIR}"/output/images/*.img.xz
  "${ARMBIAN_DIR}"/output/images/*.img.gz
  "${ARMBIAN_DIR}"/output/images/*.img
)
shopt -u nullglob

if (( ${#images[@]} == 0 )); then
  echo "Armbian did not produce an image in ${ARMBIAN_DIR}/output/images" >&2
  exit 1
fi

matching=()
for candidate in "${images[@]}"; do
  # Armbian names images like Armbian_<ver>_<board>_<release>_<branch>_<...>.
  # Matching the delimited board name avoids selecting orangepi5-plus when
  # building orangepi5 from a dirty output directory.
  if [[ "$(basename "${candidate}")" == *_"${BOARD}"_* ]]; then
    matching+=("${candidate}")
  fi
done
if (( ${#matching[@]} > 0 )); then
  images=("${matching[@]}")
fi

# Prefer an archive over a raw image when Armbian produced both, and pick the
# newest candidate within that group.
image=""
for wanted_suffix in .img.xz .img.gz .img; do
  group=()
  for candidate in "${images[@]}"; do
    if [[ "${candidate}" == *"${wanted_suffix}" ]]; then
      group+=("${candidate}")
    fi
  done
  if (( ${#group[@]} > 0 )); then
    image="$(ls -1t "${group[@]}" | head -n 1)"
    break
  fi
done

case "${image}" in
  *.img.xz) suffix=".img.xz" ;;
  *.img.gz) suffix=".img.gz" ;;
  *.img) suffix=".img" ;;
  *) suffix=".${image##*.}" ;;
esac

mkdir -p "${OUT_DIR}"
destination="${OUT_DIR}/${IMAGE_NAME}${suffix}"
cp "${image}" "${destination}"

echo "Created ${destination}"
