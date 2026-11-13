# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from typing import Any, Dict, cast
from unittest.mock import MagicMock

import msgpack
from synapselib import SynapseCamera, SynapsePipelineType
from synapselib.pipelines.apriltag import ApriltagDetection, ApriltagResult
from synapselib.pipelines.color import ColorDetection, ColorResult


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


class TestResultDecoding(unittest.TestCase):
    """Decode payloads shaped exactly like the runtime's MessagePack output."""

    @staticmethod
    def _pack(payload: Dict[str, Any]) -> bytes:
        return cast(bytes, msgpack.packb(payload, use_bin_type=True))

    def setUp(self):
        # getResults() does not touch NetworkTables, but constructing the
        # camera still needs an instance.
        import ntcore

        ntcore.NetworkTableInstance.getDefault = MagicMock(return_value=MagicMock())
        self.camera = SynapseCamera("Cam1")

    def test_apriltag_runtime_payload(self):
        payload = {
            "cameraEstimate_fieldSpace": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
            "tags": [
                {
                    "tag_id": 7,
                    "hamming": 1,
                    "tagPose_screenSpace": [320, 240],
                }
            ],
            "reprojection_error": 1.25,
        }

        result = self.camera.getResults(
            ApriltagResult, self._pack(payload)
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertIsInstance(result.tags[0], ApriltagDetection)
        self.assertEqual(result.tags[0].tag_id, 7)
        self.assertEqual(result.tags[0].hamming, 1)
        self.assertEqual(result.tags[0].tx, 320)
        self.assertEqual(result.tags[0].ty, 240)
        self.assertEqual(
            result.cameraEstimate_fieldSpace, [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        )
        self.assertIsNotNone(result.cameraEstimate_fieldSpace3d)

    def test_apriltag_without_pose(self):
        payload = {
            "cameraEstimate_fieldSpace": None,
            "tags": [],
            "reprojection_error": 0.0,
        }

        result = self.camera.getResults(
            ApriltagResult, self._pack(payload)
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertIsNone(result.cameraEstimate_fieldSpace)
        self.assertIsNone(result.cameraEstimate_fieldSpace3d)

    def test_color_runtime_payload(self):
        detection = {"bbox": [1, 2, 3, 4], "center": [2.5, 4.0], "area": 12.0}
        payload = {
            "timestamp": 1.5,
            "detections": [detection],
            "main_detection": detection,
        }

        result = self.camera.getResults(
            ColorResult, self._pack(payload)
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertIsInstance(result.detections[0], ColorDetection)
        self.assertEqual(result.detections[0].bbox, [1, 2, 3, 4])
        self.assertIsInstance(result.main_detection, ColorDetection)

    def test_color_without_main_detection(self):
        payload = {"timestamp": 1.5, "detections": [], "main_detection": None}

        result = self.camera.getResults(
            ColorResult, self._pack(payload)
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.detections, [])
        self.assertIsNone(result.main_detection)
