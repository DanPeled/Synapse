# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import json
from pathlib import Path

from synapse import __version__

ROOT = Path(__file__).resolve().parents[2]


def load_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for line in (ROOT / "versions.properties").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "!")):
            continue
        key, separator, value = line.partition("=")
        if separator:
            versions[key.strip()] = value.strip()
    return versions


def test_generated_version_module_is_in_sync() -> None:
    versions = load_versions()

    assert __version__.SYNAPSE_VERSION == versions["synapsePythonVersion"]
    assert __version__.WPILIB_VERSION == versions["wpilibPythonVersion"]
    assert __version__.WPILIB_YEAR == versions["wpilibYear"]


def test_vendordep_is_in_sync() -> None:
    versions = load_versions()
    vendordep = json.loads(
        (ROOT / "synapse_lib" / "vendordep" / "SynapseLib.json").read_text(encoding="utf-8")
    )

    assert vendordep["version"] == versions["synapseVersion"]
    year_key = "wpilibYear" if "wpilibYear" in vendordep else "frcYear"
    assert vendordep[year_key] == versions["frcYear"]
