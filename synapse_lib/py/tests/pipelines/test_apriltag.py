import unittest
from synapselib.pipelines.apriltag import (
    ApriltagPoseEstimate,
    ApriltagDetection,
    ApriltagResult,
)


class TestApriltagClasses(unittest.TestCase):
    def test_pose_estimate_equality_and_hash(self):
        a1 = ApriltagPoseEstimate(
            acceptedError=0.1,
            rejectedError=0.2,
            acceptedPose=[1, 2, 3, 0, 0, 0],
            rejectedPose=[4, 5, 6, 0, 0, 0],
        )
        a2 = ApriltagPoseEstimate(
            acceptedError=0.1,
            rejectedError=0.2,
            acceptedPose=[1, 2, 3, 0, 0, 0],
            rejectedPose=[4, 5, 6, 0, 0, 0],
        )
        self.assertEqual(a1, a2)
        self.assertEqual(hash(a1), hash(a2))

    def test_detection_equality_and_hash(self):
        pose = ApriltagPoseEstimate(0.1, 0.2, [1, 2, 3, 0, 0, 0], [4, 5, 6, 0, 0, 0])
        d1 = ApriltagDetection(
            1, 0.0, [0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0], [1, 1, 1, 0, 0, 0], pose
        )
        d2 = ApriltagDetection(
            1, 0.0, [0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0], [1, 1, 1, 0, 0, 0], pose
        )
        self.assertEqual(d1, d2)
        self.assertEqual(hash(d1), hash(d2))

    def test_result_equality_and_hash(self):
        pose = ApriltagPoseEstimate(0.1, 0.2, [1, 2, 3, 0, 0, 0], [4, 5, 6, 0, 0, 0])
        detection = ApriltagDetection(
            1, 0.0, [0, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, 0], [1, 1, 1, 0, 0, 0], pose
        )
        r1 = ApriltagResult(
            tags=[detection], robotEstimate_fieldSpace=[0, 0, 0, 0, 0, 0]
        )
        r2 = ApriltagResult(
            tags=[detection], robotEstimate_fieldSpace=[0, 0, 0, 0, 0, 0]
        )
        self.assertEqual(r1, r2)
        self.assertEqual(hash(r1), hash(r2))


if __name__ == "__main__":
    unittest.main()
