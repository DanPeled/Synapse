import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from synapse.core.pipeline import FrameResult
from synapse.core.pipeline_handler import (Pipeline, PipelineLoader,
                                           PipelineSettings)


class DummyPipeline(Pipeline[PipelineSettings]):
    __is_enabled__ = True

    def __init__(self, cameraIndex: int, settings: PipelineSettings):
        super().__init__(cameraIndex, settings)

    def processFrame(self, img, timestamp: float) -> FrameResult:
        pass


class DummySettings(PipelineSettings):
    def __init__(self, config_map=None):
        self.config_map = config_map or {}


class TestPipelineLoader(unittest.TestCase):
    def setUp(self):
        self.pipeline_dir = Path("/fake/path")
        self.loader = PipelineLoader(self.pipeline_dir)

    @patch("synapse.core.pipeline_handler.importlib.util.spec_from_file_location")
    @patch("synapse.core.pipeline_handler.importlib.util.module_from_spec")
    def test_load_pipelines_loads_enabled_classes(
        self, mock_module_from_spec, mock_spec_from_file_location
    ):
        # Prepare mocks
        dummy_module = MagicMock()
        dummy_module.DummyPipeline = DummyPipeline
        mock_spec = MagicMock()
        mock_spec.loader = MagicMock()
        mock_spec_from_file_location.return_value = mock_spec
        mock_module_from_spec.return_value = dummy_module

        mock_spec.loader.exec_module.side_effect = lambda mod: setattr(
            mod, "DummyPipeline", DummyPipeline
        )

        with patch("synapse.core.pipeline_handler.Path.rglob") as mock_rglob:
            mock_rglob.return_value = [Path("dummy_pipeline.py")]

            pipelines = self.loader.loadPipelines(Path("."))

        self.assertIn("DummyPipeline", pipelines)
        self.assertEqual(pipelines["DummyPipeline"], DummyPipeline)

    @patch("synapse.core.pipeline_handler.Config.getInstance")
    @patch("synapse.core.pipeline_handler.GlobalSettings.getCameraConfigMap")
    def test_load_pipeline_settings(self, mock_camera_config_map, mock_config_instance):
        self.loader.pipelineTypes = {"DummyPipeline": DummyPipeline}

        mock_camera_config_map.return_value = {0: MagicMock(defaultPipeline=1)}

        mock_config = MagicMock()
        mock_config.getConfigMap.return_value = {
            "pipelines": [{"type": "DummyPipeline", "settings": {"threshold": 0.5}}]
        }
        mock_config_instance.return_value = mock_config

        with patch(
            "synapse.core.pipeline_handler.resolveGenericArgument",
            return_value=DummySettings,
        ):
            self.loader.loadPipelineSettings()

        self.assertEqual(self.loader.defaultPipelineIndexes[0], 1)
        self.assertIn(0, self.loader.pipelineSettings)
        self.assertIsInstance(self.loader.pipelineSettings[0], DummySettings)

    def test_set_and_get_pipeline_instance(self):
        dummy_pipeline = DummyPipeline(0, PipelineSettings())
        self.loader.setPipelineInstance(1, dummy_pipeline)

        self.assertEqual(self.loader.getPipeline(1), dummy_pipeline)
        self.assertIsNone(self.loader.getPipeline(99))

    def test_get_pipeline_type_by_index_and_name(self):
        self.loader.pipelineTypes["DummyPipeline"] = DummyPipeline
        self.loader.pipelineTypeNames[5] = "DummyPipeline"

        self.assertEqual(self.loader.getPipelineTypeByIndex(5), DummyPipeline)
        self.assertEqual(
            self.loader.getPipelineTypeByName("DummyPipeline"), DummyPipeline
        )

    def test_get_default_pipeline(self):
        self.loader.defaultPipelineIndexes[2] = 9
        self.assertEqual(self.loader.getDefaultPipeline(2), 9)
        self.assertEqual(self.loader.getDefaultPipeline(999), 0)
