# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import math
from typing import Iterable

from wpimath.geometry import Pose3d, Quaternion, Rotation3d

from .apriltag_detector import (CameraPoseEstimate,
                                ICombinedApriltagCameraPoseEstimator)


class WeightedAverageMultiTagEstimator(ICombinedApriltagCameraPoseEstimator):
    @staticmethod
    def estimate(tags: Iterable[CameraPoseEstimate], **kwargs) -> Pose3d:
        tags = list(tags)
        if not tags:
            return Pose3d()  # identity if no detections

        # --- Weighted average translation ---
        weighted_x, weighted_y, weighted_z = 0.0, 0.0, 0.0
        total_weight = 0.0

        # Store quaternions + weights
        weighted_quats = []

        for t in tags:
            pose = t.cameraPose_fieldSpace

            # Distance from Camera to tag (in field space)
            # (You could also use camera-to-tag transform length here)
            dist = pose.translation().norm()

            # Weight = inverse distance (closer tag → higher weight)
            weight = 1.0 / max(dist, 1e-6)

            weighted_x += pose.x * weight
            weighted_y += pose.y * weight
            weighted_z += pose.z * weight
            total_weight += weight

            # Collect weighted quaternion
            rot = pose.rotation()
            q: Quaternion = rot.getQuaternion()
            weighted_quats.append((q, weight))

        # Average translation
        avg_x = weighted_x / total_weight
        avg_y = weighted_y / total_weight
        avg_z = weighted_z / total_weight

        # Weighted quaternion average
        qw, qx, qy, qz = 0.0, 0.0, 0.0, 0.0
        for q, w in weighted_quats:
            qw += q.W() * w
            qx += q.X() * w
            qy += q.Y() * w
            qz += q.Z() * w
        norm = math.sqrt(qw * qw + qx * qx + qy * qy + qz * qz)
        if norm > 1e-9:
            qw, qx, qy, qz = qw / norm, qx / norm, qy / norm, qz / norm

        avg_rot = Quaternion(qw, qx, qy, qz)

        return Pose3d(avg_x, avg_y, avg_z, Rotation3d(avg_rot))
