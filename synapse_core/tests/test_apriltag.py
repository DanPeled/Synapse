# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from typing import cast
from unittest.mock import patch

import numpy as np
from synapse.pipelines.apriltag.apriltag_detector import (
    AprilTagDetection,
    AprilTagDetector,
    drawTagDetectionMarker,
    makeCorners,
)
from synapse.pipelines.apriltag.apriltag_napa import NapaApriltagDetector
from synapse.pipelines.apriltag.field_loader import ApriltagFieldJson
from typing_extensions import Buffer

FIELD_JSON = {
    "tags": [
        {
            "ID": 1,
            "pose": {
                "translation": {"x": 1.0, "y": 2.0, "z": 3.0},
                "rotation": {"quaternion": {"W": 1.0, "X": 0.0, "Y": 0.0, "Z": 0.0}},
            },
        }
    ],
    "field": {"length": 16.0, "width": 8.0},
}


class TestApriltagFieldJson(unittest.TestCase):
    def test_loadFieldCached_reuses_loaded_field(self):
        ApriltagFieldJson.loadFieldCached.cache_clear()

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fmap.json"
            path.write_text(json.dumps(FIELD_JSON))

            with patch(
                "synapse.pipelines.apriltag.field_loader.json.load",
                wraps=json.load,
            ) as json_load:
                first = ApriltagFieldJson.loadFieldCached(path)
                second = ApriltagFieldJson.loadFieldCached(path)

        self.assertIs(first, second)
        json_load.assert_called_once()
        tagPose = first.getTagPose(1)
        self.assertIsNotNone(tagPose)
        if tagPose is not None:
            self.assertEqual(tagPose.translation().x, 1.0)


class TestDrawTagDetectionMarker(unittest.TestCase):
    def test_draws_boundary_and_center(self):
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        tag = AprilTagDetection(
            tagID=7,
            homography=(1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0),
            hamming=0,
            corners=makeCorners(10, 10, 40, 10, 40, 40, 10, 40),
            center=(25, 25),
        )

        drawTagDetectionMarker(tag, img)

        # Boundary is drawn green, center is drawn red.
        self.assertTrue(np.any(img[:, :, 1]))
        self.assertTrue(np.any(img[:, :, 2]))
        self.assertTrue(np.any(img[40, 10:41, 1]))


class _FakeNapaDetector:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.closed = False
        _FakeNapaDetector.instances.append(self)

    def detect(self, image):
        return [
            types.SimpleNamespace(
                tag_id=7,
                corners=np.array(
                    [[10.0, 20.0], [30.0, 40.0], [50.0, 60.0], [70.0, 80.0]]
                ),
                hamming=1,
                center=np.array([1.4, 2.6]),
                homography=np.array(
                    [[10.0, 0.0, 1.4], [0.0, 10.0, 2.6], [0.0, 0.0, 1.0]]
                ),
            )
        ]

    def close(self):
        self.closed = True


class TestNapaApriltagDetector(unittest.TestCase):
    def setUp(self):
        _FakeNapaDetector.instances.clear()
        module = types.ModuleType("napa_vision")
        setattr(module, "NapaDetector", _FakeNapaDetector)
        self.patcher = patch.dict(sys.modules, {"napa_vision": module})
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def test_detects_and_converts_napa_results(self):
        detector = NapaApriltagDetector()

        frame = cast(Buffer, np.zeros((100, 100), dtype=np.uint8))

        detections = detector.detect(frame)

        self.assertEqual(len(detections), 1)
        detection = detections[0]
        self.assertEqual(detection.tagID, 7)
        self.assertEqual(detection.hamming, 1)
        self.assertEqual(detection.center, (1, 3))
        self.assertEqual(
            detection.corners,
            makeCorners(30, 40, 10, 20, 70, 80, 50, 60),
        )
        self.assertEqual(
            detection.homography,
            (10.0, 0.0, 1.4, 0.0, 10.0, 2.6, 0.0, 0.0, 1.0),
        )

        kwargs = _FakeNapaDetector.instances[0].kwargs
        self.assertEqual(kwargs["family"], "tag36h11")
        self.assertEqual(kwargs["min_tag_px"], 32)
        self.assertIsNone(kwargs["max_hamming"])

    def test_setConfig_rebuilds_detector_with_napa_settings(self):
        detector = NapaApriltagDetector()
        oldDetector = _FakeNapaDetector.instances[0]

        detector.setConfig(
            AprilTagDetector.Config(
                minTagPx=16,
                maxHamming=2,
                minContrast=30,
                minBorderCells=10,
                sharpening=0.5,
                maxDetections=12,
            )
        )

        self.assertTrue(oldDetector.closed)
        kwargs = _FakeNapaDetector.instances[-1].kwargs
        self.assertEqual(kwargs["min_tag_px"], 16)
        self.assertEqual(kwargs["max_hamming"], 2)
        self.assertEqual(kwargs["min_contrast"], 30)
        self.assertEqual(kwargs["min_border_cells"], 10)
        self.assertEqual(kwargs["sharpening"], 0.5)
        self.assertEqual(kwargs["max_detections"], 12)

    def test_setFamily_rebuilds_detector(self):
        detector = NapaApriltagDetector()
        oldDetector = _FakeNapaDetector.instances[0]

        detector.setFamily("tag16h5")

        self.assertTrue(oldDetector.closed)
        self.assertEqual(_FakeNapaDetector.instances[-1].kwargs["family"], "tag16h5")


if __name__ == "__main__":
    unittest.main()
