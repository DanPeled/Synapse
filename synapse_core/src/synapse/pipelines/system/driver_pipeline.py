# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Optional, Tuple, Union

import cv2
from synapse.core.pipeline import (
    CameraSettings,
    Pipeline,
    PipelineResult,
    PipelineSettings,
    SynapseCamera,
    pipelineName,
)
from synapse.core.settings_api import (
    NumberConstraint,
    Setting,
    SettingsValue,
    settingField,
)
from synapse.stypes import CameraID, Frame


class DriverPipelineSettings(PipelineSettings):
    # percentage from center: -100% (left/top) to +100% (right/bottom)
    crosshair_x = settingField(NumberConstraint(-100, 100, 0.1), 0.0)
    crosshair_y = settingField(NumberConstraint(-100, 100, 0.1), 0.0)


@pipelineName("DriverViewPipeline")
class DriverPipeline(Pipeline[DriverPipelineSettings, PipelineResult]):
    def __init__(self, settings: DriverPipelineSettings):
        super().__init__(settings)
        # Resolution parsing and crosshair coordinate math only depend on
        # settings. Cache the result until one of those settings changes so
        # the per-frame path is just two cv2.line calls.
        self._crosshairKey: Optional[Tuple[str, float, float]] = None
        self._crosshairGeometry: Optional[Tuple[int, int, int]] = None

    def updateConstraints(self) -> None:
        # Percent values are resolution-agnostic → no updates needed
        pass

    def bind(self, cameraIndex: CameraID, camera: SynapseCamera) -> None:
        super().bind(cameraIndex, camera)
        self._invalidateCrosshairCache()

    def setCameraSetting(
        self, setting: Union[str, Setting], value: SettingsValue
    ) -> None:
        super().setCameraSetting(setting, value)
        settingKey = getattr(setting, "key", setting)
        if settingKey == CameraSettings.resolution.key:
            self._invalidateCrosshairCache()

    def onSettingChanged(self, setting: Setting, value: SettingsValue) -> None:
        settingKey = getattr(setting, "key", setting)
        if settingKey in (
            self.settings.crosshair_x.key,
            self.settings.crosshair_y.key,
        ):
            self._invalidateCrosshairCache()

    def _invalidateCrosshairCache(self) -> None:
        self._crosshairKey = None
        self._crosshairGeometry = None

    def _crosshairGeometryNow(self) -> Tuple[int, int, int]:
        if self._crosshairKey is None:
            res = self.getCameraSetting(CameraSettings.resolution)
            cxPct = self.getSetting(self.settings.crosshair_x)
            cyPct = self.getSetting(self.settings.crosshair_y)
            self._crosshairKey = (res, float(cxPct), float(cyPct))

        if self._crosshairGeometry is None:
            res, cxPct, cyPct = self._crosshairKey
            wStr, hStr = res.split("x", 1)
            width, height = int(wStr), int(hStr)

            # Convert percentage-from-center → pixels.
            x = int(width / 2 + (cxPct / 100) * (width / 2))
            y = int(height / 2 + (cyPct / 100) * (height / 2))
            size = max(10, min(width, height) // 50)  # auto scales with resolution
            self._crosshairGeometry = (x, y, size)

        return self._crosshairGeometry

    def processFrame(self, img, timestamp: float) -> Frame:
        x, y, size = self._crosshairGeometryNow()

        # ========== DRAW CROSSHAIR ==========
        color = (0, 255, 0)  # green
        thickness = 2

        # horizontal line
        cv2.line(img, (x - size, y), (x + size, y), color, thickness)
        # vertical line
        cv2.line(img, (x, y - size), (x, y + size), color, thickness)

        return img
