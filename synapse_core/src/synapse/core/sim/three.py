# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Three.js camera coordinate transforms for the simulated headless renderer.

The renderer lives in ``synapse_sim/`` and uses the same field model/tag
config as the viewer. These helpers convert WPIlib field coordinates and
camera poses into the values consumed by ``headless/renderer.js``.
"""

from __future__ import annotations

import math
from typing import Any, Dict

from wpimath.geometry import Pose3d, Rotation3d

from .model import cameraMatrix

#: Field dimensions as used by the viewer (inches converted).
L_METERS = 651.22 * 0.0254
W_METERS = 317.677 * 0.0254


def _rot3d_to_numpy(R: Rotation3d):
    """Return the 3x3 rotation matrix for a wpimath Rotation3d."""
    # wpimath's Rotation3d exposes toMatrix(); prefer it when available.
    if hasattr(R, "toMatrix"):
        M = R.toMatrix()
        # Depending on bindings it may return a numpy array or a wpimath matrix.
        try:
            import numpy as np

            return np.array(M)
        except Exception:
            return [
                [M[0, 0], M[0, 1], M[0, 2]],
                [M[1, 0], M[1, 1], M[1, 2]],
                [M[2, 0], M[2, 1], M[2, 2]],
            ]
    q = R.getQuaternion()
    # Quaternion to matrix
    w, x, y, z = float(q.W()), float(q.X()), float(q.Y()), float(q.Z())
    # Normalize defensively
    n = math.sqrt(w * w + x * x + y * y + z * z)
    if n == 0:
        w, x, y, z = 1.0, 0.0, 0.0, 0.0
    else:
        w, x, y, z = w / n, x / n, y / n, z / n
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z
    return [
        [1 - 2 * (yy + zz), 2 * (xy - wz), 2 * (xz + wy)],
        [2 * (xy + wz), 1 - 2 * (xx + zz), 2 * (yz - wx)],
        [2 * (xz - wy), 2 * (yz + wx), 1 - 2 * (xx + yy)],
    ]


def _mat_mul(a, b):
    return [
        [
            a[0][0] * b[0][0] + a[0][1] * b[1][0] + a[0][2] * b[2][0],
            a[0][0] * b[0][1] + a[0][1] * b[1][1] + a[0][2] * b[2][1],
            a[0][0] * b[0][2] + a[0][1] * b[1][2] + a[0][2] * b[2][2],
        ],
        [
            a[1][0] * b[0][0] + a[1][1] * b[1][0] + a[1][2] * b[2][0],
            a[1][0] * b[0][1] + a[1][1] * b[1][1] + a[1][2] * b[2][1],
            a[1][0] * b[0][2] + a[1][1] * b[1][2] + a[1][2] * b[2][2],
        ],
        [
            a[2][0] * b[0][0] + a[2][1] * b[1][0] + a[2][2] * b[2][0],
            a[2][0] * b[0][1] + a[2][1] * b[1][1] + a[2][2] * b[2][1],
            a[2][0] * b[0][2] + a[2][1] * b[1][2] + a[2][2] * b[2][2],
        ],
    ]


def _mat_transpose(a):
    return [
        [a[0][0], a[1][0], a[2][0]],
        [a[0][1], a[1][1], a[2][1]],
        [a[0][2], a[1][2], a[2][2]],
    ]


def _quat_from_rotmat(R):
    # Convert rotation matrix to quaternion (w, x, y, z)
    tr = R[0][0] + R[1][1] + R[2][2]
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2
        w = 0.25 * s
        x = (R[2][1] - R[1][2]) / s
        y = (R[0][2] - R[2][0]) / s
        z = (R[1][0] - R[0][1]) / s
    elif R[0][0] > R[1][1] and R[0][0] > R[2][2]:
        s = math.sqrt(1.0 + R[0][0] - R[1][1] - R[2][2]) * 2
        w = (R[2][1] - R[1][2]) / s
        x = 0.25 * s
        y = (R[0][1] + R[1][0]) / s
        z = (R[0][2] + R[2][0]) / s
    elif R[1][1] > R[2][2]:
        s = math.sqrt(1.0 + R[1][1] - R[0][0] - R[2][2]) * 2
        w = (R[0][2] - R[2][0]) / s
        x = (R[0][1] + R[1][0]) / s
        y = 0.25 * s
        z = (R[1][2] + R[2][1]) / s
    else:
        s = math.sqrt(1.0 + R[2][2] - R[0][0] - R[1][1]) * 2
        w = (R[1][0] - R[0][1]) / s
        x = (R[0][2] + R[2][0]) / s
        y = (R[1][2] + R[2][1]) / s
        z = 0.25 * s
    n = math.sqrt(w * w + x * x + y * y + z * z)
    if n == 0:
        return (1.0, 0.0, 0.0, 0.0)
    return (w / n, x / n, y / n, z / n)


def wpi_camera_to_three(cameraPose: Pose3d):
    """Convert a WPIlib camera pose to Three.js camera position/quaternion.

    Verified in the implementation plan:
    - position = [L/2 - x, z, y - W/2]
    - R_three = M @ R_wpi @ B, with
      M = [[-1,0,0],[0,0,1],[0,1,0]] and B = [[0,0,-1],[-1,0,0],[0,1,0]]
    """
    L = L_METERS
    W = W_METERS
    t = cameraPose.translation()
    x = float(t.X())
    y = float(t.Y())
    z = float(t.Z())

    # Centered field coordinates match the viewer's coordinate mapping.
    three_x = L / 2.0 - x
    three_y = z
    three_z = y - W / 2.0

    R_wpi = _rot3d_to_numpy(cameraPose.rotation())
    M = [[-1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, 1.0, 0.0]]
    B = [[0.0, 0.0, -1.0], [-1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]
    R_three = _mat_mul(_mat_mul(M, R_wpi), B)
    # Three.js expects world quaternion; the renderer uses camera.quaternion.
    # The math above matches the plan; ensure we pass [x,y,z,w].
    qw, qx, qy, qz = _quat_from_rotmat(R_three)
    return [three_x, three_y, three_z], [qx, qy, qz, qw]


def camera_fov_y(width: int, height: int, horizontal_fov_deg: float = 70.0) -> float:
    hfov = math.radians(horizontal_fov_deg)
    vfov = 2.0 * math.atan(math.tan(hfov / 2.0) * (height / width))
    return math.degrees(vfov)


def camera_intrinsics(width: int, height: int):
    intr = cameraMatrix(int(width), int(height))
    fx = float(intr[0][0])
    fy = float(intr[1][1])
    cx = float(intr[0][2])
    cy = float(intr[1][2])
    return {"fx": fx, "fy": fy, "cx": cx, "cy": cy}


def camera_spec(
    index: int,
    width: int,
    height: int,
    cameraPose: Pose3d,
    seq: int = 0,
) -> Dict[str, Any]:
    position, quat = wpi_camera_to_three(cameraPose)
    return {
        "index": int(index),
        "width": int(width),
        "height": int(height),
        "position": position,
        "quaternion": quat,
        "fovY": camera_fov_y(width, height),
        "intrinsics": camera_intrinsics(width, height),
        "seq": int(seq),
    }
