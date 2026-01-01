# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import json
from typing import Dict, Optional

from wpimath.geometry import Pose3d, Quaternion, Rotation3d, Translation3d


class ApriltagFieldJson:
    TagId = int

    def __init__(self, jsonDict: Dict[TagId, Pose3d], length: float, width: float):
        self.fieldMap = jsonDict
        self.length = length
        self.width = width

    @staticmethod
    def loadField(filePath: str) -> "ApriltagFieldJson":
        with open(filePath, "r") as file:
            jsonDict: dict = json.load(file)
            tagsDict: Dict[ApriltagFieldJson.TagId, Pose3d] = {}
            for tag in jsonDict.get("tags", {}):
                poseDict = tag["pose"]
                rotation = poseDict["rotation"]["quaternion"]
                translation = poseDict["translation"]
                tagsDict[tag["ID"]] = Pose3d(
                    translation=Translation3d(
                        translation["x"], translation["y"], translation["z"]
                    ),
                    rotation=Rotation3d(
                        Quaternion(
                            w=rotation["W"],
                            x=rotation["X"],
                            y=rotation["Y"],
                            z=rotation["Z"],
                        )
                    ),
                )
            length = jsonDict["field"]["length"]
            width = jsonDict["field"]["width"]
            return ApriltagFieldJson(tagsDict, length, width)

    def getTagPose(self, id: TagId) -> Optional[Pose3d]:
        if id in self.fieldMap.keys():
            return self.fieldMap[id]
        else:
            return None
