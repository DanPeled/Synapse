# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from synapse.pipelines.apriltag.apriltag_detector import (
    AprilTagDetection, drawTagDetectionMarker, makeCorners)
from synapse.pipelines.apriltag.field_loader import ApriltagFieldJson

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
        self.assertEqual(first.getTagPose(1).translation().x, 1.0)


class TestDrawTagDetectionMarker(unittest.TestCase):
    def test_draws_boundary_and_center(self):
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        tag = AprilTagDetection(
            tagID=7,
            homography=(1.0,) * 9,
            hamming=0,
            corners=makeCorners(10, 10, 40, 10, 40, 40, 10, 40),
            center=(25, 25),
        )

        drawTagDetectionMarker(tag, img)

        # Boundary is drawn green, center is drawn red.
        self.assertTrue(np.any(img[:, :, 1]))
        self.assertTrue(np.any(img[:, :, 2]))
        self.assertTrue(np.any(img[40, 10:41, 1]))


if __name__ == "__main__":
    unittest.main()
