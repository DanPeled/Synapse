# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from unittest.mock import MagicMock

from synapselib import SynapseCamera, SynapsePipelineType
from synapselib.pipelines.apriltag import ApriltagResult


class TestSynapsePipeline(unittest.TestCase):
    def test_pipeline_properties(self):
        pipeline = SynapsePipelineType(ApriltagResult, "TestPipeline")
        self.assertEqual(pipeline.typestring, "TestPipeline")
        self.assertEqual(pipeline.getResultType().__class__.__name__, "type")  # pyright: ignore


class TestSynapseCamera(unittest.TestCase):
    def setUp(self):
        # Mock NTCore tables and entries
        self.mock_entry = MagicMock()
        self.mock_table = MagicMock()
        self.mock_table.getEntry.return_value = self.mock_entry
        self.mock_instance = MagicMock()
        self.mock_instance.getTable.return_value.getSubTable.return_value = (
            self.mock_table
        )

        # Patch NTCore instance
        import ntcore

        ntcore.NetworkTableInstance.getDefault = MagicMock(
            return_value=self.mock_instance
        )

        self.camera = SynapseCamera("Cam1")

    def test_pipeline_set_get(self):
        self.camera.setPipeline(5)
        self.mock_entry.setInteger.assert_called_with(5)
        self.mock_entry.getInteger.return_value = 5
        self.assertEqual(self.camera.getPipeline(), 5)

    def test_recording_status(self):
        self.mock_entry.getBoolean.return_value = True
        self.assertTrue(self.camera.getRecordingStatus())
        self.camera.setRecordStatus(False)
        self.mock_entry.setBoolean.assert_called_with(False)

    def test_get_pipeline_type(self):
        self.mock_entry.getString.return_value = "ApriltagPipeline"
        self.camera._SynapseCamera__pipelineTypeEntry = self.mock_entry  # pyright: ignore
        self.assertEqual(self.camera.getPipelineType(), "ApriltagPipeline")
