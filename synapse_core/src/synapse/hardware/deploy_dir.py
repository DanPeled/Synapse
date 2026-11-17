# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from builtins import classmethod
from pathlib import Path


class DeployDirectory:
    @classmethod
    def setup(cls, path: Path):
        cls.path: Path = path

    @classmethod
    def getDir(cls) -> Path:
        return cls.path
