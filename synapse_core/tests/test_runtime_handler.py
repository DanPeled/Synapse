# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

from ntcore import ValueEventData
from synapse import Pipeline, PipelineSettings
from synapse.core.pipeline import FrameResult, PipelineResult
from synapse.core.runtime_handler import RuntimeManager


class DummyPipeline(Pipeline[PipelineSettings, PipelineResult]):
    __is_enabled__ = True

    def __init__(self, settings: PipelineSettings):
        super().__init__(settings)

    def processFrame(self, img, timestamp: float) -> FrameResult:
        pass


class DummySettings(PipelineSettings):
    def __init__(self, config_map=None):
        self.config_map = config_map or {}


class TestRuntimeManager(unittest.TestCase):
    def setUp(self):
        self.mock_camera_handler = MagicMock()

        with patch(
            "synapse.core.runtime_handler.CameraHandler",
            return_value=self.mock_camera_handler,
        ):
            self.handler = RuntimeManager(directory=Path("."))

    def test_assign_default_pipelines(self):
        self.mock_camera_handler.cameras = {0: "Camera0", 1: "Camera1"}
        self.handler.pipelineHandler.getDefaultPipeline = MagicMock(
            side_effect=[10, 20]
        )
        self.handler.setPipelineByIndex = MagicMock()

        self.handler.assignDefaultPipelines()

        self.handler.setPipelineByIndex.assert_any_call(cameraIndex=0, pipelineIndex=10)
        self.handler.setPipelineByIndex.assert_any_call(cameraIndex=1, pipelineIndex=20)
        self.assertEqual(self.handler.setPipelineByIndex.call_count, 2)

    def test_set_pipeline_by_index_invalid_camera(self):
        self.mock_camera_handler.cameras = {0: "Camera0"}
        self.handler.pipelineHandler.pipelineTypeNames = {0: {1: "PipelineA"}}

        with patch("synapse.core.runtime_handler.log.err") as mock_log:
            self.handler.setPipelineByIndex(cameraIndex=5, pipelineIndex=1)
            mock_log.assert_called_once()

    def test_get_event_data_value_bool(self):
        mock_event = MagicMock()
        type_prop = PropertyMock(return_value="Boolean")
        value = MagicMock(getBoolean=MagicMock(return_value=True))
        mock_event.data.__class__ = ValueEventData
        mock_event.data.topic.getType = type_prop
        mock_event.data.value = value

        with patch("synapse.core.runtime_handler.NetworkTableType.kBoolean", "Boolean"):
            result = self.handler.getEventDataValue(mock_event)
            self.assertTrue(result)

    def test_setup_calls_all_components(self):
        with (
            patch.object(self.handler.pipelineHandler, "setup") as setup_loader,
            patch.object(self.handler.cameraHandler, "setup") as setup_cameras,
            patch.object(self.handler, "assignDefaultPipelines") as assign_defaults,
            patch.object(self.handler, "setupNetworkTables") as setup_nt,
            patch.object(self.handler, "startMetricsThread") as start_metrics,
        ):
            self.handler.setup(directory=Path("."))

            setup_loader.assert_called_once()
            setup_cameras.assert_called_once()
            assign_defaults.assert_called_once()
            setup_nt.assert_called_once()
            start_metrics.assert_called_once()


if __name__ == "__main__":
    unittest.main()
