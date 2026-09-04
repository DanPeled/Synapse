# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest

from synapselib.pipelines.apriltag import ApriltagDetection, ApriltagResult


class TestApriltagClasses(unittest.TestCase):
    def test_detection_equality_and_hash(self):
        d1 = ApriltagDetection(
            1,
            0.0,
            [0, 0],
        )
        d2 = ApriltagDetection(1, 0.0, [0, 0])
        self.assertEqual(d1, d2)
        self.assertEqual(hash(d1), hash(d2))

    def test_result_equality_and_hash(self):
        detection = ApriltagDetection(1, 0.0, [0, 0])
        r1 = ApriltagResult(
            tags=[detection],
            cameraEstimate_fieldSpace=[0, 0, 0, 0, 0, 0],
            reprojection_error=0.0,
        )
        r2 = ApriltagResult(
            tags=[detection],
            cameraEstimate_fieldSpace=[0, 0, 0, 0, 0, 0],
            reprojection_error=0.0,
        )
        self.assertEqual(r1, r2)
        self.assertEqual(hash(r1), hash(r2))


if __name__ == "__main__":
    unittest.main()
