# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Generated from schema/synapse_lib.json. Do not edit by hand.
# Run `python tools/generate_synapse_lib.py` to regenerate.

from typing import Final

SETTINGS_TABLE: Final[str] = "settings"
DATA_TABLE: Final[str] = "data"

PIPELINE: Final[str] = "pipeline"
RECORD: Final[str] = "record"
PIPELINE_TYPE: Final[str] = "pipeline_type"
RESULTS: Final[str] = "results"
CAPTURE_LATENCY: Final[str] = "captureLatency"
PROCESS_LATENCY: Final[str] = "processLatency"

BRIGHTNESS_SETTING: Final[str] = "brightness"
GAIN_SETTING: Final[str] = "gain"
EXPOSURE_SETTING: Final[str] = "exposure"
ORIENTATION_SETTING: Final[str] = "orientation"

APRILTAG_PIPELINE: Final[str] = "ApriltagPipeline"
COLOR_PIPELINE: Final[str] = "ColorPipeline"
