# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Example pipeline that draws markers loaded from a user-selected JSON file.

This pipeline demonstrates the ``FileConstraint`` setting. Instead of storing a
fixed path in code, the target file is chosen from the pipeline settings in the
Synapse UI. The value is stored relative to the project root, which is the same
root used by the file server, so existing files can be selected and new files
can be uploaded directly from the UI.

The file is loaded when the pipeline starts and reloaded whenever the
``target_file`` setting changes. Empty, missing, or malformed files are reported
through the pipeline results without interrupting the camera stream.

Example JSON file::

    {
      "targets": [
        {
          "name": "Red Speaker",
          "x": 0.25,
          "y": 0.5,
          "radius": 28,
          "color": [40, 40, 220]
        }
      ]
    }

``x`` and ``y`` are normalized frame coordinates (0 to 1), ``radius`` is in
pixels, and ``color`` is a BGR triplet.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Tuple

import cv2
from synapse import Pipeline, PipelineSettings
from synapse.core.config import Config
from synapse.core.pipeline import PipelineResult
from synapse.core.settings_api import (
    BooleanConstraint,
    FileConstraint,
    NumberConstraint,
    Setting,
    SettingsValue,
    settingField,
)
from synapse.log import info, warn
from synapse.stypes import Frame

DEFAULT_RADIUS = 24
DEFAULT_COLOR = (0, 200, 0)


# ---------------- Settings ---------------- #
class TargetOverlaySettings(PipelineSettings):
    target_file = settingField(
        FileConstraint(path="config", fileTypes=["json"]),
        default="config/targets.json",
        description="JSON file with the targets to draw over the camera feed",
        category="Target Overlay",
    )
    draw_labels = settingField(
        BooleanConstraint(),
        default=True,
        description="Draw the target name next to each marker",
        category="Target Overlay",
    )
    marker_thickness = settingField(
        NumberConstraint(1, 10, 1),
        default=2,
        description="Thickness of the marker outlines",
        category="Target Overlay",
    )


# ---------------- Results ---------------- #
@dataclass
class OverlayTarget:
    name: str
    x: float
    y: float
    radius: int
    color: Tuple[int, int, int]


@dataclass
class TargetOverlayResult(PipelineResult):
    loaded: bool
    file: str
    count: int
    error: str
    targets: List[OverlayTarget]


# ---------------- Helpers ---------------- #
def _projectRoot() -> Path:
    """Resolve file setting values against the Synapse project root."""
    try:
        return Config.getInstance().path.parent.parent
    except (AttributeError, TypeError):
        return Path.cwd()


def _clampColorChannel(value: Any) -> int:
    return max(0, min(255, int(value)))


def _parseColor(value: Any) -> Tuple[int, int, int]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return DEFAULT_COLOR

    try:
        return (
            _clampColorChannel(value[0]),
            _clampColorChannel(value[1]),
            _clampColorChannel(value[2]),
        )
    except (TypeError, ValueError):
        return DEFAULT_COLOR


def _parseTargets(data: Any) -> List[OverlayTarget]:
    if not isinstance(data, dict):
        raise ValueError("Expected the file to contain a JSON object")

    rawTargets = data.get("targets")
    if not isinstance(rawTargets, list):
        raise ValueError("Expected a 'targets' list in the file")

    targets: List[OverlayTarget] = []
    for index, rawTarget in enumerate(rawTargets):
        if not isinstance(rawTarget, dict):
            raise ValueError(f"Target #{index} must be a JSON object")

        try:
            x = float(rawTarget["x"])
            y = float(rawTarget["y"])
        except KeyError as e:
            raise ValueError(f"Target #{index} is missing the {e} field") from e
        except (TypeError, ValueError) as e:
            raise ValueError(f"Target #{index} has an invalid x/y value") from e

        try:
            radius = max(1, int(rawTarget.get("radius", DEFAULT_RADIUS)))
        except (TypeError, ValueError) as e:
            raise ValueError(f"Target #{index} has an invalid radius") from e

        targets.append(
            OverlayTarget(
                name=str(rawTarget.get("name", f"Target {index}")),
                x=min(max(x, 0.0), 1.0),
                y=min(max(y, 0.0), 1.0),
                radius=radius,
                color=_parseColor(rawTarget.get("color")),
            )
        )

    return targets


# ---------------- Pipeline ---------------- #
class TargetOverlayPipeline(Pipeline[TargetOverlaySettings, TargetOverlayResult]):
    def __init__(self, settings: TargetOverlaySettings):
        super().__init__(settings)
        self._targets: List[OverlayTarget] = []
        self._result = TargetOverlayResult(
            False, "", 0, "Target file has not been loaded yet", []
        )
        self._loadTargets()

    def _loadTargets(self) -> None:
        fileValue = self.getSetting(self.settings.target_file)
        relativePath = fileValue.strip() if isinstance(fileValue, str) else ""

        if not relativePath:
            self._targets = []
            self._result = TargetOverlayResult(
                False, "", 0, "No target file selected", []
            )
            return

        path = Path(relativePath)
        if not path.is_absolute():
            path = _projectRoot() / path

        try:
            with open(path, "r", encoding="utf-8") as file:
                targets = _parseTargets(json.load(file))
        except (OSError, ValueError) as e:
            warn(f"Failed to load target file '{relativePath}': {e}")
            self._targets = []
            self._result = TargetOverlayResult(False, relativePath, 0, str(e), [])
            return

        info(f"Loaded {len(targets)} targets from '{relativePath}'")
        self._targets = targets
        self._result = TargetOverlayResult(
            True, relativePath, len(targets), "", targets
        )

    def onSettingChanged(self, setting: Setting, value: SettingsValue) -> None:
        if setting.key == self.settings.target_file.key:
            self._loadTargets()

    def processFrame(self, img, timestamp: float) -> Frame:
        self.setResults(self._result)

        if not self._targets:
            return img

        height, width = img.shape[:2]
        thickness = max(1, int(self.getSetting(self.settings.marker_thickness)))
        drawLabels = bool(self.getSetting(self.settings.draw_labels))

        for target in self._targets:
            center = (int(target.x * width), int(target.y * height))
            cv2.circle(img, center, target.radius, target.color, thickness)

            crosshair = max(4, target.radius // 2)
            cv2.line(
                img,
                (center[0] - crosshair, center[1]),
                (center[0] + crosshair, center[1]),
                target.color,
                thickness,
            )
            cv2.line(
                img,
                (center[0], center[1] - crosshair),
                (center[0], center[1] + crosshair),
                target.color,
                thickness,
            )

            if drawLabels and target.name:
                origin = (
                    center[0] + target.radius + 4,
                    center[1] - target.radius,
                )
                cv2.putText(
                    img,
                    target.name,
                    origin,
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    target.color,
                    thickness,
                    cv2.LINE_AA,
                )

        return img
