# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from synapse.core.synapse import Synapse


def test_create_and_run_starts_and_shuts_down_runtime():
    with (
        patch("synapse.core.synapse.RuntimeManager"),
        patch("synapse.core.synapse.Synapse") as synapseType,
    ):
        synapse = synapseType.return_value
        synapse.init.return_value = True

        Synapse.createAndRunRuntime(Path("."), False)

    synapse.init.assert_called_once()
    synapse.run.assert_called_once()
    synapse.shutdown.assert_called_once()


def test_create_and_run_shuts_down_when_init_fails():
    with (
        patch("synapse.core.synapse.RuntimeManager"),
        patch("synapse.core.synapse.Synapse") as synapseType,
    ):
        synapse = synapseType.return_value
        synapse.init.return_value = False

        Synapse.createAndRunRuntime(Path("."))

    synapse.run.assert_not_called()
    synapse.shutdown.assert_called_once()


def test_create_and_run_shuts_down_on_exception():
    with (
        patch("synapse.core.synapse.RuntimeManager"),
        patch("synapse.core.synapse.Synapse") as synapseType,
    ):
        synapse = synapseType.return_value
        synapse.init.side_effect = RuntimeError("init failed")

        with pytest.raises(RuntimeError, match="init failed"):
            Synapse.createAndRunRuntime(Path("."))

    synapse.shutdown.assert_called_once()


def test_create_and_run_shuts_down_on_keyboard_interrupt():
    with (
        patch("synapse.core.synapse.RuntimeManager"),
        patch("synapse.core.synapse.Synapse") as synapseType,
    ):
        synapse = synapseType.return_value
        synapse.init.return_value = True
        synapse.run.side_effect = KeyboardInterrupt()

        Synapse.createAndRunRuntime(Path("."))

    synapse.shutdown.assert_called_once()


def test_synapse_close_and_cleanup_alias_shutdown():
    synapse = Synapse(sendSettingsInNT=False)
    synapse.shutdown = MagicMock()

    synapse.close()
    synapse.cleanup()

    assert synapse.shutdown.call_count == 2
