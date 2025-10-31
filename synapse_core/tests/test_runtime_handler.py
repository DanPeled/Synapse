# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, PropertyMock, patch

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
        self.handler.pipelineHandler.pipelineTypeNames = {1: "PipelineA"}

        with patch("synapse.core.runtime_handler.log.err") as mock_log:
            self.handler.setPipelineByIndex(cameraIndex=5, pipelineIndex=1)
            mock_log.assert_called_once()

    def test_set_pipeline_by_index_invalid_pipeline(self):
        self.mock_camera_handler.cameras = {0: "Camera0"}
        self.handler.pipelineHandler.pipelineTypeNames = {1: "PipelineA"}
        self.handler.pipelineBindings = {0: 1}
        self.handler.setNTPipelineIndex = MagicMock()

        with patch("synapse.core.runtime_handler.log.err") as mock_log:
            self.handler.setPipelineByIndex(cameraIndex=0, pipelineIndex=99)
            mock_log.assert_called_once()
            self.handler.setNTPipelineIndex.assert_called_with(0, 1)

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

    def test_to_dict_and_save(self):
        # Setup fake camera config and pipeline binding
        fake_config = MagicMock()
        fake_config.toDict.return_value = {"mock": "camera_config"}
        fake_pipeline = MagicMock()
        fake_pipeline.toDict.return_value = {"mock": "pipeline_config"}

        with patch(
            "synapse.core.global_settings.GlobalSettings.getCameraConfigMap"
        ) as mock_camera_map:
            mock_camera_map.return_value = {0: fake_config}
            self.handler.pipelineHandler.pipelineInstanceBindings = {0: fake_pipeline}
            self.handler.pipelineHandler.pipelineTypeNames = {0: "mock"}

            result_dict = self.handler.toDict()
            assert "global" in result_dict
            assert "network" in result_dict
            assert "pipelines" in result_dict

    def test_remove_pipeline_auto_bind(self):
        """
        Tests logic for automatic binding for cameras that use a removed pipeline
        """
        with (
            patch(
                "synapse.core.runtime_handler.getCameraTableName",
                return_value="FakeCamera",
            ),
            patch(
                "synapse.core.runtime_handler.getCameraTable", return_value=MagicMock()
            ),
        ):
            on_removed = Mock()
            self.handler.pipelineHandler.onRemovePipeline.add(on_removed)
            self.handler.setupCallbacks()

            self.mock_camera_handler.cameras = {0: Mock()}
            self.mock_camera_handler.cameras[0].name = "yeepers"

            self.handler.pipelineHandler.pipelineTypes["AnotherDummy"] = DummyPipeline
            self.handler.pipelineHandler.addPipeline(
                index=5, name="New Pipeline", typename="AnotherDummy", settings={}
            )
            self.handler.pipelineHandler.setDefaultPipeline(0, 5)

            self.handler.pipelineHandler.pipelineTypes["DummyPipeline"] = DummyPipeline
            self.handler.pipelineHandler.pipelineTypeNames[5] = "DummyPipeline"

            self.assertEqual(
                self.handler.pipelineHandler.getPipelineTypeByIndex(5), DummyPipeline
            )
            self.assertEqual(
                self.handler.pipelineHandler.getPipelineTypeByName("DummyPipeline"),
                DummyPipeline,
            )

            self.handler.pipelineHandler.addPipeline(
                index=7, name="New Pipeline", typename="AnotherDummy", settings={}
            )
            self.handler.pipelineBindings[0] = 7
            self.handler.setPipelineByIndex(0, 7)
            self.handler.pipelineHandler.removePipeline(7)

            on_removed.assert_called_once()
            called_args = on_removed.call_args[0]
            self.assertEqual(called_args[0], 7)
            self.assertEqual(self.handler.pipelineBindings[0], 5)


if __name__ == "__main__":
    unittest.main()
