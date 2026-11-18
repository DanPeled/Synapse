#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Small helpers shared by the image build wrappers.

# Print the Synapse version from the source tree.
synapse_version() {
  local repo_root="$1"
  python3 - "${repo_root}" <<'PY'
import pathlib
import re
import sys

version_file = pathlib.Path(sys.argv[1]) / "synapse_core/src/synapse/__version__.py"
text = version_file.read_text()
match = re.search(r'SYNAPSE_VERSION\s*:\s*Final\[str\]\s*=\s*"([^"]+)"', text)
if not match:
    raise SystemExit(f"Could not find SYNAPSE_VERSION in {version_file}")
print(match.group(1))
PY
}

# Check out a pinned upstream ref into <dir>. Works for tags, branches, and
# commits, and reuses an existing checkout so repeated builds are cheap.
checkout_ref() {
  local url="$1"
  local ref="$2"
  local dir="$3"

  if [[ ! -d "${dir}/.git" ]]; then
    mkdir -p "${dir}"
    git -C "${dir}" init -q
  fi

  if git -C "${dir}" remote get-url origin >/dev/null 2>&1; then
    git -C "${dir}" remote set-url origin "${url}"
  else
    git -C "${dir}" remote add origin "${url}"
  fi

  echo "Checking out ${url} at ${ref}..." >&2
  git -C "${dir}" fetch --depth 1 origin "${ref}" >&2
  git -C "${dir}" checkout --force --detach FETCH_HEAD >&2
}

# Resolve the wheel to install. Prefers SYNAPSE_WHEEL, then the newest wheel in
# dist/. The wheel is not built here: a complete wheel also needs the UI and
# simulator assets, so callers run `make build` (or the release workflow).
ensure_synapse_wheel() {
  local repo_root="$1"
  local wheels=()

  if [[ -n "${SYNAPSE_WHEEL:-}" ]]; then
    if [[ ! -f "${SYNAPSE_WHEEL}" ]]; then
      echo "SYNAPSE_WHEEL does not exist: ${SYNAPSE_WHEEL}" >&2
      return 1
    fi
    printf '%s\n' "${SYNAPSE_WHEEL}"
    return 0
  fi

  shopt -s nullglob
  wheels=("${repo_root}"/dist/synapsefrc-*.whl)
  shopt -u nullglob

  if (( ${#wheels[@]} == 0 )); then
    echo "No release wheel found in ${repo_root}/dist." >&2
    echo "Run 'make build' first, or pass SYNAPSE_WHEEL." >&2
    return 1
  fi

  ls -1t "${wheels[@]}" | head -n 1
}
