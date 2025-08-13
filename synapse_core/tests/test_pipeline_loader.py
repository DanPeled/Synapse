# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from synapse.core.pipeline import FrameResult
from synapse.core.runtime_handler import (Pipeline, PipelineLoader,
                                          PipelineSettings)


class DummyPipeline(Pipeline[PipelineSettings]):
    __is_enabled__ = True

    def __init__(self, settings: PipelineSettings):
        super().__init__(settings)

    def processFrame(self, img, timestamp: float) -> FrameResult:
        pass


class DummySettings(PipelineSettings):
    def __init__(self, config_map=None):
        self.config_map = config_map or {}


class TestPipelineLoader(unittest.TestCase):
    def setUp(self):
        self.pipeline_dir = Path("/fake/path")
        self.loader = PipelineLoader(self.pipeline_dir)

    @patch("synapse.core.runtime_handler.importlib.util.spec_from_file_location")
    @patch("synapse.core.runtime_handler.importlib.util.module_from_spec")
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

        with patch("synapse.core.runtime_handler.Path.rglob") as mock_rglob:
            mock_rglob.return_value = [Path("dummy_pipeline.py")]

            pipelines = self.loader.loadPipelineTypes(Path("."))

        self.assertIn("DummyPipeline", pipelines)
        self.assertEqual(pipelines["DummyPipeline"], DummyPipeline)

    @patch("synapse.core.runtime_handler.Config.getInstance")
    @patch("synapse.core.runtime_handler.GlobalSettings.getCameraConfigMap")
    def test_load_pipeline_settings(self, mock_camera_config_map, mock_config_instance):
        self.loader.pipelineTypes = {"DummyPipeline": DummyPipeline}

        mock_camera_config_map.return_value = {0: MagicMock(defaultPipeline=1)}

        mock_config = MagicMock()
        mock_config.getConfigMap.return_value = {
            "pipelines": [
                {
                    "type": "DummyPipeline",
                    "name": "yeepy",
                    "settings": {"threshold": 0.5},
                }
            ]
        }
        mock_config_instance.return_value = mock_config

        with patch(
            "synapse.core.runtime_handler.resolveGenericArgument",
            return_value=DummySettings,
        ):
            self.loader.loadPipelineSettings()

        self.assertEqual(self.loader.defaultPipelineIndexes[0], 1)
        self.assertIn(0, self.loader.pipelineSettings)
        self.assertIsInstance(self.loader.pipelineSettings[0], DummySettings)

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

    def test_set_pipeline_while_running(self):
        self.loader.pipelineTypes["DummyPipeline"] = DummyPipeline
        self.loader.pipelineTypeNames[5] = "DummyPipeline"

        self.assertEqual(self.loader.getPipelineTypeByIndex(5), DummyPipeline)
        self.assertEqual(
            self.loader.getPipelineTypeByName("DummyPipeline"), DummyPipeline
        )

        self.loader.pipelineTypes["AnotherDummy"] = DummyPipeline
        self.loader.addPipeline(
            index=5, name="New Pipeline", typename="AnotherDummy", settings={}
        )

        pipeline = self.loader.pipelineInstanceBindings.get(5, None)

        self.assertIsNotNone(pipeline)
        if pipeline is not None:
            self.assertEqual(pipeline.name, "New Pipeline")
            self.assertEqual(self.loader.pipelineTypeNames.get(5), "AnotherDummy")

    def test_add_pipeline(self):
        self.assertIsNone(self.loader.getPipeline(5))

        self.loader.pipelineTypes["AnotherDummy"] = DummyPipeline
        self.loader.addPipeline(
            index=5, name="New Pipeline", typename="AnotherDummy", settings={}
        )

        pipeline = self.loader.pipelineInstanceBindings.get(5, None)

        self.assertIsNotNone(pipeline)

        if pipeline is not None:
            self.assertEqual(pipeline.name, "New Pipeline")
            self.assertEqual(self.loader.pipelineTypeNames.get(5), "AnotherDummy")

    def test_add_then_remove_pipeline(self):
        self.loader.pipelineTypes["AnotherDummy"] = DummyPipeline
        self.loader.addPipeline(
            index=5, name="New Pipeline", typename="AnotherDummy", settings={}
        )

        pipeline = self.loader.pipelineInstanceBindings.get(5, None)

        self.assertIsNotNone(pipeline)
        if pipeline is not None:
            self.assertEqual(pipeline.name, "New Pipeline")
            self.assertEqual(self.loader.pipelineTypeNames.get(5), "AnotherDummy")

            removedpipeline = self.loader.removePipeline(5)
            self.assertIsNotNone(removedpipeline)

            if removedpipeline is not None:
                self.assertIsNone(self.loader.getPipeline(5))
                self.assertEqual(removedpipeline.name, "New Pipeline")

    def test_on_add_pipeline(self):
        on_add = Mock()

        self.loader.pipelineTypes["AnotherDummy"] = DummyPipeline
        self.loader.addPipeline(
            index=5, name="New Pipeline", typename="AnotherDummy", settings={}
        )

        pipeline = self.loader.pipelineInstanceBindings.get(5, None)

        on_add.assert_not_called()
        self.assertIsNotNone(pipeline)

        if pipeline is not None:
            self.assertEqual(pipeline.name, "New Pipeline")
            self.assertEqual(self.loader.pipelineTypeNames.get(5), "AnotherDummy")

            self.loader.onAddPipeline.add(on_add)

            self.loader.pipelineTypes["DummyPipeline"] = DummyPipeline
            self.loader.pipelineTypeNames[5] = "DummyPipeline"

            self.assertEqual(self.loader.getPipelineTypeByIndex(5), DummyPipeline)
            self.assertEqual(
                self.loader.getPipelineTypeByName("DummyPipeline"), DummyPipeline
            )

            self.loader.pipelineTypes["AnotherDummy"] = DummyPipeline
            self.loader.addPipeline(
                index=7, name="New Pipeline", typename="AnotherDummy", settings={}
            )

            on_add.assert_called_once()
            called_args = on_add.call_args[0]
            self.assertEqual(called_args[0], 7)

    def test_on_remove_pipeline(self):
        on_removed = Mock()

        self.loader.pipelineTypes["AnotherDummy"] = DummyPipeline
        self.loader.addPipeline(
            index=5, name="New Pipeline", typename="AnotherDummy", settings={}
        )

        self.loader.pipelineInstanceBindings.get(5, None)

        on_removed.assert_not_called()

        self.loader.onRemovePipeline.add(on_removed)

        self.loader.pipelineTypes["DummyPipeline"] = DummyPipeline
        self.loader.pipelineTypeNames[5] = "DummyPipeline"

        self.assertEqual(self.loader.getPipelineTypeByIndex(5), DummyPipeline)
        self.assertEqual(
            self.loader.getPipelineTypeByName("DummyPipeline"), DummyPipeline
        )

        self.loader.pipelineTypes["AnotherDummy"] = DummyPipeline
        self.loader.addPipeline(
            index=7, name="New Pipeline", typename="AnotherDummy", settings={}
        )
        self.loader.removePipeline(7)

        on_removed.assert_called_once()
        called_args = on_removed.call_args[0]
        self.assertEqual(called_args[0], 7)
