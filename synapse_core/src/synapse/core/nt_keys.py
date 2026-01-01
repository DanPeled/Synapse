# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from enum import Enum


class NTKeys(Enum):
    kSettings = "settings"
    kMetrics = "metrics"
    kProcessLatency = "processLatency"
    kCaptureLatency = "captureLatency"
