# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import cv2
from synapse.core.pipeline import (CameraSettings, Pipeline, PipelineResult,
                                   PipelineSettings, SynapseCamera,
                                   pipelineName)
from synapse.core.settings_api import NumberConstraint, settingField
from synapse.stypes import CameraID, Frame


class DriverPipelineSettings(PipelineSettings):
    # percentage from center: -100% (left/top) to +100% (right/bottom)
    crosshair_x = settingField(NumberConstraint(-100, 100, 0.1), 0.0)
    crosshair_y = settingField(NumberConstraint(-100, 100, 0.1), 0.0)


@pipelineName("DriverViewPipeline")
class DriverPipeline(Pipeline[DriverPipelineSettings, PipelineResult]):
    def __init__(self, settings: DriverPipelineSettings):
        super().__init__(settings)

    def updateConstraints(self) -> None:
        # Percent values are resolution-agnostic → no updates needed
        pass

    def bind(self, cameraIndex: CameraID, camera: SynapseCamera) -> None:
        super().bind(cameraIndex, camera)

    def processFrame(self, img, timestamp: float) -> Frame:
        # Get resolution
        res = self.getCameraSetting(CameraSettings.resolution)
        w_str, h_str = res.split("x", 1)
        width, height = int(w_str), int(h_str)

        # Get percentage settings
        cx_pct = self.getSetting(self.settings.crosshair_x)  # -100 → +100
        cy_pct = self.getSetting(self.settings.crosshair_y)

        # Convert percentage-from-center → pixels
        x = int(width / 2 + (cx_pct / 100) * (width / 2))
        y = int(height / 2 + (cy_pct / 100) * (height / 2))

        # ========== DRAW CROSSHAIR ==========
        size = max(10, min(width, height) // 50)  # auto scales with resolution

        color = (0, 255, 0)  # green
        thickness = 2

        # horizontal line
        cv2.line(img, (x - size, y), (x + size, y), color, thickness)
        # vertical line
        cv2.line(img, (x, y - size), (x, y + size), color, thickness)

        return img
