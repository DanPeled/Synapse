from typing import List
from wpimath import geometry
from .log import err


def listToTransform3d(dataList: List[List[float]]) -> geometry.Transform3d:
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
