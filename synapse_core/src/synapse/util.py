from typing import List

from wpimath import geometry

from .log import err


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
