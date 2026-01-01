# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from synapse.core.pipeline import FrameResult, PipelineResult
from synapse.core.pipeline_handler import (Pipeline, PipelineHandler,
                                           PipelineSettings)


class DummyPipeline(Pipeline[PipelineSettings, PipelineResult]):
    __is_enabled__ = True

    def __init__(self, settings: PipelineSettings):
        super().__init__(settings)

    def processFrame(self, img, timestamp: float) -> FrameResult:
        pass


class DummySettings(PipelineSettings):
    def __init__(self, config_map=None):
        self.config_map = config_map or {}


class TestPipelineHandler(unittest.TestCase):
    def setUp(self):
        self.pipeline_dir = Path("/fake/path")
        self.loader = PipelineHandler(self.pipeline_dir)
        # Ensure camera 0 is initialized since tests expect it
        self.loader.onAddCamera(0, "cam0", MagicMock())

    @patch("synapse.core.pipeline_handler.importlib.util.spec_from_file_location")
    @patch("synapse.core.pipeline_handler.importlib.util.module_from_spec")
    def test_load_pipelines_loads_enabled_classes(
        self, mock_module_from_spec, mock_spec_from_file_location
    ):
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

            pipelines = self.loader.loadPipelineTypes(Path("."))

        self.assertIn("DummyPipeline", pipelines)
        self.assertEqual(pipelines["DummyPipeline"], DummyPipeline)

    def test_get_pipeline_type_by_index_and_name(self):
        self.loader.pipelineTypeNames[0][5] = "DummyPipeline"
        self.loader.pipelineTypesViaName["DummyPipeline"] = DummyPipeline

        self.assertEqual(self.loader.getPipelineTypeByIndex(5, 0), DummyPipeline)
        self.assertEqual(
            self.loader.getPipelineTypeByName("DummyPipeline"), DummyPipeline
        )

    def test_get_default_pipeline(self):
        self.loader.defaultPipelineIndexes[2] = 9
        self.assertEqual(self.loader.getDefaultPipeline(2), 9)
        self.assertEqual(self.loader.getDefaultPipeline(999), 0)

    def test_set_pipeline_while_running(self):
        self.loader.pipelineTypesViaName["DummyPipeline"] = DummyPipeline
        self.loader.pipelineTypeNames[0][5] = "DummyPipeline"

        self.assertEqual(self.loader.getPipelineTypeByIndex(5, 0), DummyPipeline)

        self.loader.pipelineTypesViaName["AnotherDummy"] = DummyPipeline
        self.loader.addPipeline(
            index=5,
            name="New Pipeline",
            typename="AnotherDummy",
            cameraid=0,
            settings={},
        )

        pipeline = self.loader.pipelineInstanceBindings[0].get(5)

        self.assertIsNotNone(pipeline)
        if pipeline:
            self.assertEqual(pipeline.name, "New Pipeline")
            self.assertEqual(self.loader.pipelineTypeNames[0].get(5), "AnotherDummy")

    def test_add_pipeline(self):
        self.assertIsNone(self.loader.getPipeline(5, 0))

        self.loader.pipelineTypesViaName["AnotherDummy"] = DummyPipeline
        self.loader.addPipeline(
            index=5,
            name="New Pipeline",
            typename="AnotherDummy",
            cameraid=0,
            settings={},
        )

        pipeline = self.loader.pipelineInstanceBindings[0].get(5)

        self.assertIsNotNone(pipeline)
        if pipeline:
            self.assertEqual(pipeline.name, "New Pipeline")
            self.assertEqual(self.loader.pipelineTypeNames[0].get(5), "AnotherDummy")

    def test_add_then_remove_pipeline(self):
        self.loader.pipelineTypesViaName["AnotherDummy"] = DummyPipeline
        self.loader.addPipeline(
            index=5,
            name="New Pipeline",
            typename="AnotherDummy",
            cameraid=0,
            settings={},
        )

        pipeline = self.loader.pipelineInstanceBindings[0].get(5)
        self.assertIsNotNone(pipeline)

        removed = self.loader.removePipeline(5, cameraid=0)
        self.assertIsNotNone(removed)

        if removed:
            self.assertIsNone(self.loader.getPipeline(5, 0))
            self.assertEqual(removed.name, "New Pipeline")

    def test_on_add_pipeline(self):
        on_add = Mock()

        self.loader.pipelineTypesViaName["AnotherDummy"] = DummyPipeline
        self.loader.addPipeline(
            index=5,
            name="New Pipeline",
            typename="AnotherDummy",
            cameraid=0,
            settings={},
        )

        self.loader.onAddPipeline.add(on_add)

        self.loader.addPipeline(
            index=7, name="Another", typename="AnotherDummy", cameraid=0, settings={}
        )

        on_add.assert_called_once()
        called_args = on_add.call_args[0]
        self.assertEqual(called_args[0], 7)

    def test_on_remove_pipeline(self):
        on_removed = Mock()

        self.loader.pipelineTypesViaName["AnotherDummy"] = DummyPipeline
        self.loader.addPipeline(
            index=5,
            name="New Pipeline",
            typename="AnotherDummy",
            cameraid=0,
            settings={},
        )

        self.loader.onRemovePipeline.add(on_removed)

        self.loader.removePipeline(5, cameraid=0)

        on_removed.assert_called_once()
        self.assertEqual(on_removed.call_args[0][0], 5)
