# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest.mock import MagicMock, patch

import numpy as np
from synapse.core.pipeline import CameraSettings
from synapse.pipelines.system.driver_pipeline import (
    DriverPipeline,
    DriverPipelineSettings,
)


def test_driver_pipeline_caches_crosshair_geometry_until_settings_change() -> None:
    pipeline = DriverPipeline(DriverPipelineSettings())
    pipeline.setCameraSetting(CameraSettings.resolution, "640x480")
    image = np.zeros((480, 640, 3), dtype=np.uint8)

    with patch("synapse.pipelines.system.driver_pipeline.cv2.line") as drawLine:
        pipeline.processFrame(image, 0.0)
        assert drawLine.call_args_list[0].args[1] == (310, 240)
        assert drawLine.call_args_list[0].args[2] == (330, 240)

        # A warm cache must not re-read settings or recompute coordinates.
        originalGetCameraSetting = pipeline.getCameraSetting
        originalGetSetting = pipeline.getSetting
        pipeline.getCameraSetting = MagicMock()
        pipeline.getSetting = MagicMock()
        pipeline.processFrame(image, 0.0)
        pipeline.getCameraSetting.assert_not_called()
        pipeline.getSetting.assert_not_called()
        assert drawLine.call_count == 4
        pipeline.getCameraSetting = originalGetCameraSetting
        pipeline.getSetting = originalGetSetting

        # Setting changes invalidate the cached geometry and update the values.
        pipeline.setSetting(pipeline.settings.crosshair_x, 50.0)
        pipeline.processFrame(image, 0.0)
        assert drawLine.call_args_list[-1].args[1] == (480, 230)
        assert drawLine.call_args_list[-1].args[2] == (480, 250)

        pipeline.setCameraSetting(CameraSettings.resolution, "320x240")
        pipeline.processFrame(image, 0.0)
        assert drawLine.call_args_list[-1].args[1] == (240, 110)
        assert drawLine.call_args_list[-1].args[2] == (240, 130)
