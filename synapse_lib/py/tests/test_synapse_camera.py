# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
import warnings
from dataclasses import dataclass
from typing import Any, Dict, List, cast
from unittest.mock import MagicMock

import msgpack
from ntcore import NetworkTableInstance
from wpimath import Pose3d, Rotation2d, Translation3d

from synapselib import SynapseCamera, SynapsePipelineType
from synapselib._synapse_camera import Setting
from synapselib.pipelines.apriltag import ApriltagDetection, ApriltagResult
from synapselib.pipelines.color import ColorDetection, ColorResult


@dataclass
class _CustomDetection:
    pose: Pose3d
    rotation: Rotation2d
    translation: Translation3d


@dataclass
class _CustomResult:
    detections: List[_CustomDetection]


class TestSynapsePipeline(unittest.TestCase):
    def test_pipeline_properties(self):
        pipeline = SynapsePipelineType(ApriltagResult, "TestPipeline")
        self.assertEqual(pipeline.typestring, "TestPipeline")
        self.assertEqual(pipeline.getResultType().__class__.__name__, "type")  # pyright: ignore


class TestSynapseCamera(unittest.TestCase):
    def setUp(self):
        self.instance = NetworkTableInstance.getDefault()
        self.instance.startLocal()
        self.table = self.instance.getTable("Synapse").getSubTable("Cam1")
        self.camera = SynapseCamera("Cam1")

    def tearDown(self):
        self.camera.close()
        self.instance.stopLocal()

    def test_pipeline_set_get(self):
        self.camera.setPipeline(5)
        self.instance.flush()
        self.assertEqual(self.camera.getPipeline(), 5)
        self.assertIsNotNone(self.camera.pipelineSubscriber)

    def test_recording_status(self):
        self.camera.setRecordStatus(True)
        self.instance.flush()
        self.assertTrue(self.camera.getRecordingStatus())
        self.camera.setRecordStatus(False)
        self.instance.flush()
        self.assertFalse(self.camera.getRecordingStatus())
        self.assertIsNotNone(self.camera.recordStateSubscriber)

    def test_get_pipeline_type(self):
        publisher = self.table.getStringTopic(
            SynapseCamera.NetworkTableTopics.kPipelineTypeTopic
        ).publish()
        publisher.set("ApriltagPipeline")
        self.instance.flush()
        self.assertEqual(self.camera.getPipelineType(), "ApriltagPipeline")
        self.assertIsNotNone(self.camera.pipelineTypeSubscriber)
        publisher.close()

    def test_cached_entries_are_keyed_by_full_topic_path(self):
        settings = self.instance.getTable("/Synapse/CacheTest/settings")
        data = self.instance.getTable("/Synapse/CacheTest/data")

        self.camera.getCachedEntry("value", settings)
        self.camera.getCachedEntry("value", data)
        self.camera.getCachedEntry("value", settings)

        self.assertEqual(len(self.camera.entryCache), 2)
        self.assertIn("/Synapse/CacheTest/settings/value", self.camera.entryCache)
        self.assertIn("/Synapse/CacheTest/data/value", self.camera.entryCache)

    def test_settings_use_one_latest_value_subscriber_per_topic(self):
        settings = self.instance.getTable("/Synapse/SubscriberTest/settings")
        publisher = settings.getDoubleTopic(Setting.kBrightness.key).publish()
        publisher.set(0.75)
        self.instance.flush()
        self.camera.settingsTable = settings

        self.assertEqual(self.camera.getSetting(Setting.kBrightness), 0.75)
        self.assertEqual(self.camera.getSetting(Setting.kBrightness), 0.75)
        self.assertEqual(len(self.camera.settingSubscribers), 1)
        publisher.close()

    def test_type_mismatch_is_reported_only_once_per_setting(self):
        settings = self.instance.getTable("/Synapse/MismatchTest/settings")
        publisher = settings.getStringTopic(Setting.kBrightness.key).publish()
        publisher.set("wrong")
        self.instance.flush()
        self.camera.settingsTable = settings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            self.assertIsNone(self.camera.getSetting(Setting.kBrightness))
            self.assertIsNone(self.camera.getSetting(Setting.kBrightness))

        self.assertEqual(len(caught), 1)
        self.assertEqual(len(self.camera.warnedSettingKeys), 1)
        publisher.close()


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

        result = self.camera.getResults(ApriltagResult, self._pack(payload))

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
        pose = result.cameraEstimate_fieldSpace3d
        self.assertIsNotNone(pose)
        assert pose is not None
        # The runtime sends roll/pitch/yaw in degrees.
        self.assertAlmostEqual(pose.rotation().x_degrees, 4.0)
        self.assertAlmostEqual(pose.rotation().y_degrees, 5.0)
        self.assertAlmostEqual(pose.rotation().z_degrees, 6.0)

    def test_apriltag_without_pose(self):
        payload = {
            "cameraEstimate_fieldSpace": None,
            "tags": [],
            "reprojection_error": 0.0,
        }

        result = self.camera.getResults(ApriltagResult, self._pack(payload))

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

        result = self.camera.getResults(ColorResult, self._pack(payload))

        self.assertIsNotNone(result)
        assert result is not None
        self.assertIsInstance(result.detections[0], ColorDetection)
        self.assertEqual(result.detections[0].bbox, [1, 2, 3, 4])
        self.assertIsInstance(result.main_detection, ColorDetection)

    def test_color_without_main_detection(self):
        payload = {"timestamp": 1.5, "detections": [], "main_detection": None}

        result = self.camera.getResults(ColorResult, self._pack(payload))

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.detections, [])
        self.assertIsNone(result.main_detection)

    def test_custom_result_with_geometry(self):
        """Custom result types can declare WPILib geometry fields."""
        payload = {
            "detections": [
                {
                    "pose": [1, 2, 3, 4, 5, 6],
                    "rotation": 90.0,
                    "translation": [7, 8, 9],
                }
            ]
        }

        result = self.camera.getResults(_CustomResult, self._pack(payload))

        self.assertIsNotNone(result)
        assert result is not None
        detection = result.detections[0]
        self.assertIsInstance(detection, _CustomDetection)
        self.assertIsInstance(detection.pose, Pose3d)
        self.assertAlmostEqual(detection.pose.x, 1.0)
        self.assertAlmostEqual(detection.pose.z, 3.0)
        self.assertAlmostEqual(detection.pose.rotation().x_degrees, 4.0)
        self.assertAlmostEqual(detection.pose.rotation().y_degrees, 5.0)
        self.assertAlmostEqual(detection.pose.rotation().z_degrees, 6.0)
        self.assertIsInstance(detection.translation, Translation3d)
        self.assertAlmostEqual(detection.translation.x, 7.0)
        self.assertAlmostEqual(detection.translation.z, 9.0)
        self.assertIsInstance(detection.rotation, Rotation2d)
        self.assertAlmostEqual(detection.rotation.degrees(), 90.0)
