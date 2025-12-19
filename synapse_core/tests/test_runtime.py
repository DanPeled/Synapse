# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path
from unittest.mock import MagicMock

from synapse.core.runtime_handler import RuntimeManager
from synapse.core.synapse import Synapse


def test_synapse_run_called_when_init_succeeds():
    root = Path(__file__).parent
    handler = RuntimeManager(root)
    s = Synapse()

    s.init = MagicMock(return_value=True)
    s.run = MagicMock()

    if s.init(handler, root / "config" / "settings.yml"):
        s.run()

    s.run.assert_called_once()
