# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Minimal project installed on Synapse release images.

Edit this file, add pipelines under ``pipelines/``, and deploy changes with
``python -m synapse_installer deploy``.
"""

import os
from pathlib import Path

from synapse.core.synapse import Synapse

if __name__ == "__main__":
    Synapse.createAndRunRuntime(root=Path(os.getcwd()))
