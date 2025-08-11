# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import socket
import typing
from typing import List, Optional, Type

from wpimath import geometry

from .core.pipeline import Pipeline
from .log import err


def getIP() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    ip: Optional[str] = None
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except OSError:
        ip = "127.0.0.1"

    s.close()

    return ip or "127.0.0.1"


def listToTransform3d(dataList: List[List[float]]) -> geometry.Transform3d:
    """
    Converts a 2D list containing position and rotation data into a Transform3d object.

    The input list must contain exactly two sublists:
    - The first sublist represents the translation (x, y, z).
    - The second sublist represents the rotation (roll, pitch, yaw) in degrees.

    Args:
        dataList (List[List[float]]): A list with two elements, each being a list of three floats.

    Returns:
        geometry.Transform3d: The resulting Transform3d object. Returns an identity transform
        if the input list does not contain exactly two elements.
    """
    if len(dataList) != 2:
        err("Invalid transform length")
        return geometry.Transform3d()
    else:
        poseList = dataList[0]
        rotationList = dataList[1]

        return geometry.Transform3d(
            translation=geometry.Translation3d(poseList[0], poseList[1], poseList[2]),
            rotation=geometry.Rotation3d.fromDegrees(
                rotationList[0], rotationList[1], rotationList[2]
            ),
        )


def transform3dToList(transform: geometry.Transform3d) -> List[List[float]]:
    """
    Converts a Transform3d object into a 2D list containing position and rotation data.

    The output list contains two sublists:
    - The first sublist represents the translation (x, y, z).
    - The second sublist represents the rotation (roll, pitch, yaw) in degrees.

    Args:
        transform (geometry.Transform3d): The Transform3d object to convert.

    Returns:
        List[List[float]]: A 2D list with translation and rotation values.
    """
    translation = transform.translation()
    rotation = transform.rotation()

    return [
        [translation.x, translation.y, translation.z],
        [
            rotation.x_degrees,  # Roll
            rotation.y_degrees,  # Pitch
            rotation.z_degrees,  # Yaw
        ],
    ]


def resolveGenericArgument(cls) -> Optional[Type]:
    orig_bases = getattr(cls, "__orig_bases__", ())
    for base in orig_bases:
        if typing.get_origin(base) is Pipeline:
            args = typing.get_args(base)
            if args:
                return args[0]
    return None
