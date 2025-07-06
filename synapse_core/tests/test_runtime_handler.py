import unittest
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

from synapse.core.runtime_handler import RuntimeManager


class TestRuntimeManager(unittest.TestCase):
    def setUp(self):
        self.mock_loader = MagicMock()
        self.mock_camera_handler = MagicMock()

        with (
            patch(
                "synapse.core.runtime_handler.PipelineLoader",
                return_value=self.mock_loader,
            ),
            patch(
                "synapse.core.runtime_handler.CameraHandler",
                return_value=self.mock_camera_handler,
            ),
        ):
            self.handler = RuntimeManager(directory=Path("."))

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

        with patch("synapse.core.runtime_handler.log.err") as mock_log:
            self.handler.setPipelineByIndex(cameraIndex=5, pipelineIndex=1)
            mock_log.assert_called_once()

    def test_set_pipeline_by_index_invalid_pipeline(self):
        self.mock_camera_handler.cameras = {0: "Camera0"}
        self.mock_loader.pipelineTypeNames = {1: "PipelineA"}
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
        mock_event.data.topic.getType = type_prop
        mock_event.data.value = value

        with patch("synapse.core.runtime_handler.NetworkTableType.kBoolean", "Boolean"):
            result = self.handler.getEventDataValue(mock_event)
            self.assertTrue(result)

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

    def test_to_dict_and_save(self):
        # Setup fake camera config and pipeline binding
        fake_config = MagicMock()
        fake_config.toDict.return_value = {"mock": "camera_config"}
        self.mock_loader.pipelineTypeNames = {"pipe1": "MockType"}
        fake_pipeline = MagicMock()
        fake_pipeline.toDict.return_value = {"mock": "pipeline_config"}

        with patch(
            "synapse.core.runtime_handler.GlobalSettings.getCameraConfigMap"
        ) as mock_camera_map:
            mock_camera_map.return_value = {0: fake_config}
            self.mock_loader.pipelineInstanceBindings = {0: fake_pipeline}
            self.mock_loader.pipelineTypeNames = {0: "mock"}

            expected_dict = {
                "global": {"camera_configs": {0: {"mock": "camera_config"}}},
                "pipelines": {0: {"mock": "pipeline_config"}},
            }

            # Test toDict
            result_dict = self.handler.toDict()
            self.assertEqual(result_dict, expected_dict)

            # Test save (write to a temp path)
            with patch(
                "builtins.open",
                new_callable=unittest.mock.mock_open,  # pyright: ignore
            ) as mock_open:
                with patch("yaml.safe_dump") as mock_yaml_dump:
                    self.handler.save()
                    mock_yaml_dump.assert_called_once_with(
                        expected_dict,
                        default_flow_style=None,
                        sort_keys=False,
                        indent=2,
                        width=80,
                    )
                    mock_open.assert_called_once()  # Ensure a file write was attempted


if __name__ == "__main__":
    unittest.main()
