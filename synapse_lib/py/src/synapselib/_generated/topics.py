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
VIEW_ID: Final[str] = "view_id"

BRIGHTNESS_SETTING: Final[str] = "brightness"
GAIN_SETTING: Final[str] = "gain"
EXPOSURE_SETTING: Final[str] = "exposure"
ORIENTATION_SETTING: Final[str] = "orientation"
CONTRAST_SETTING: Final[str] = "contrast"
SATURATION_SETTING: Final[str] = "saturation"
HUE_SETTING: Final[str] = "hue"
WHITE_BALANCE_TEMPERATURE_SETTING: Final[str] = "white_balance_temperature"
SHARPNESS_SETTING: Final[str] = "sharpness"

APRILTAG_PIPELINE: Final[str] = "ApriltagPipeline"
COLOR_PIPELINE: Final[str] = "ColorPipeline"
