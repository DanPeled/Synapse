# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Simulated field camera used by ``synapse --sim``."""

from .camera import SimCamera
from .setup import installSimulation

__all__ = ["SimCamera", "installSimulation"]
