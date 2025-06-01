import unittest
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

from synapse.core.pipeline_handler import PipelineHandler


class TestPipelineHandler(unittest.TestCase):
    def setUp(self):
        self.mock_loader = MagicMock()
        self.mock_camera_handler = MagicMock()

        with (
            patch(
                "synapse.core.pipeline_handler.PipelineLoader",
                return_value=self.mock_loader,
            ),
            patch(
                "synapse.core.pipeline_handler.CameraHandler",
                return_value=self.mock_camera_handler,
            ),
        ):
            self.handler = PipelineHandler(directory=Path("."))

    def test_assign_default_pipelines(self):
        self.mock_camera_handler.cameras = {0: "Camera0", 1: "Camera1"}
        self.mock_loader.getDefaultPipeline.side_effect = [10, 20]

        self.handler.setPipelineByIndex = MagicMock()

        self.handler.assignDefaultPipelines()

        self.handler.setPipelineByIndex.assert_any_call(cameraIndex=0, pipelineIndex=10)
        self.handler.setPipelineByIndex.assert_any_call(cameraIndex=1, pipelineIndex=20)
        self.assertEqual(self.handler.setPipelineByIndex.call_count, 2)

    def test_set_pipeline_by_index_invalid_camera(self):
        self.mock_camera_handler.cameras = {0: "Camera0"}
        self.mock_loader.pipelineTypeNames = {1: "PipelineA"}

        with patch("synapse.core.pipeline_handler.log.err") as mock_log:
            self.handler.setPipelineByIndex(cameraIndex=5, pipelineIndex=1)
            mock_log.assert_called_once()

    def test_set_pipeline_by_index_invalid_pipeline(self):
        self.mock_camera_handler.cameras = {0: "Camera0"}
        self.mock_loader.pipelineTypeNames = {1: "PipelineA"}
        self.handler.pipelineBindings = {0: 1}
        self.handler.setNTPipelineIndex = MagicMock()

        with patch("synapse.core.pipeline_handler.log.err") as mock_log:
            self.handler.setPipelineByIndex(cameraIndex=0, pipelineIndex=99)
            mock_log.assert_called_once()
            self.handler.setNTPipelineIndex.assert_called_with(0, 1)

    def test_get_event_data_value_bool(self):
        mock_event = MagicMock()
        type_prop = PropertyMock(return_value="Boolean")
        value = MagicMock(getBoolean=MagicMock(return_value=True))
        mock_event.data.topic.getType = type_prop
        mock_event.data.value = value

        with patch(
            "synapse.core.pipeline_handler.NetworkTableType.kBoolean", "Boolean"
        ):
            result = self.handler.getEventDataValue(mock_event)
            self.assertTrue(result)

    def test_set_nt_pipeline_index(self):
        mock_entry = MagicMock()

        with patch(
            "synapse.core.pipeline_handler.NetworkTableInstance.getDefault"
        ) as mock_nt:
            mock_table = MagicMock()
            mock_nt.return_value.getTable.return_value = mock_table
            mock_table.getEntry.return_value = mock_entry

            self.handler.setNTPipelineIndex(cameraIndex=0, pipelineIndex=42)

            mock_table.getEntry.assert_called_once()
            mock_entry.setInteger.assert_called_with(42)

    def test_setup_calls_all_components(self):
        with (
            patch.object(self.handler.pipelineLoader, "setup") as setup_loader,
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
