# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import json
from dataclasses import dataclass
from enum import Enum
from functools import cache, lru_cache
from typing import Any, Dict, Final, List, Optional, Set, Union

import cv2
import numpy as np
import robotpy_apriltag as apriltag
import synapse.log as log
from cv2.typing import MatLike
from synapse.core.global_settings import GlobalSettings
from synapse.core.pipeline import (FrameResult, Pipeline, pipelineResult,
                                   pipelineSettings)
from synapse.core.settings_api import (BooleanConstraint, EnumeratedConstraint,
                                       NumberConstraint, settingField)
from synapse.stypes import CameraID, Frame
from wpimath import geometry, units
from wpimath.geometry import (Pose2d, Pose3d, Quaternion, Rotation3d,
                              Transform3d, Translation3d)


@dataclass
class RobotPoseEstimate:
    robotPose_tagSpace: Transform3d
    robotPose_fieldSpace: Pose3d


@pipelineResult
class ApriltagResult:
    detection: apriltag.AprilTagDetection
    timestamp: float
    robotPoseEstimate: RobotPoseEstimate
    tagPoseEstimate: apriltag.AprilTagPoseEstimate


class ApriltagVerbosity(Enum):
    kPoseOnly = 0
    kTagDetails = 1
    kTagDetectionData = 2
    kAll = 3

    @classmethod
    def fromValue(cls, value: int) -> "ApriltagVerbosity":
        if value == 0:
            return cls.kPoseOnly
        if value == 1:
            return cls.kTagDetails
        if value == 2:
            return cls.kTagDetectionData
        if value == 3:
            return cls.kAll
        return cls.kPoseOnly


@cache
def getIgnoredDataByVerbosity(verbosity: ApriltagVerbosity) -> Optional[Set[str]]:
    if verbosity == ApriltagVerbosity.kAll:
        return None

    ignored: Set[str] = set()

    if verbosity.value <= ApriltagVerbosity.kTagDetectionData.value:
        ignored.update({"corners", "homography", "center"})
    if verbosity.value <= ApriltagVerbosity.kTagDetails.value:
        ignored.update({"pose_err", "decision_margin", ApriltagPipeline.kHammingKey})
    if verbosity.value <= ApriltagVerbosity.kPoseOnly.value:
        ignored.update(
            {ApriltagPipelineSettings.tag_family.key, ApriltagPipeline.kTagIDKey}
        )

    return ignored


@pipelineSettings
class ApriltagPipelineSettings:
    tag_size = settingField(
        NumberConstraint(minValue=0, maxValue=None), default=units.meters(0.1651)
    )
    tag_family = settingField(
        EnumeratedConstraint(["tag36h11", "tag16h5"]), default="tag36h11"
    )
    stick_to_ground = settingField(BooleanConstraint(), default=False)
    fieldpose = settingField(BooleanConstraint(), default=True)
    verbosity = settingField(
        EnumeratedConstraint(options=[ver.value for ver in ApriltagVerbosity]),
        default=ApriltagVerbosity.kPoseOnly.value,
    )
    num_threads = settingField(NumberConstraint(minValue=1, maxValue=6), default=1)


class ApriltagPipeline(Pipeline[ApriltagPipelineSettings, ApriltagResult]):
    kHammingKey: Final[str] = "hamming"
    kTagIDKey: Final[str] = "tag_id"
    kMeasuredMatrixResolutionKey: Final[str] = "measured_res"
    kRobotPoseFieldSpaceKey: Final[str] = "robotPose_fieldSpace"
    kRobotPoseTagSpaceKey: Final[str] = "robotPose_tagSpace"
    kTagPoseEstimateKey: Final[str] = "tag_estimate"
    kTagPoseFieldSpaceKey: Final[str] = "tagPose_fieldSpace"
    kTagCenterKey: Final[str] = "tagPose_screenSpace"

    def __init__(self, settings: ApriltagPipelineSettings):
        super().__init__(settings)
        self.settings: ApriltagPipelineSettings = settings
        ApriltagPipeline.fmap = ApriltagFieldJson.loadField("config/fmap.json")

    def bind(self, cameraIndex: CameraID):
        self.cameraMatrix: List[List[float]] = (
            self.getCameraMatrix(cameraIndex) or np.eye(3).tolist()
        )

        self.distCoeffs = self.getDistCoeffs(cameraIndex)
        self.camera_transform = self.getCameraTransform(cameraIndex)
        self.apriltagDetector: apriltag.AprilTagDetector = apriltag.AprilTagDetector()

        detectorConfig: apriltag.AprilTagDetector.Config = (
            apriltag.AprilTagDetector.Config()
        )

        detectorConfig.numThreads = int(
            self.settings.getSetting(ApriltagPipelineSettings.num_threads)
        )
        self.apriltagDetector.setConfig(detectorConfig)
        self.apriltagDetector.addFamily(
            self.settings.getSetting(ApriltagPipelineSettings.tag_family)
        )
        self.poseEstimator: apriltag.AprilTagPoseEstimator = (
            apriltag.AprilTagPoseEstimator(
                config=apriltag.AprilTagPoseEstimator.Config(
                    tagSize=(
                        self.settings.getSetting(ApriltagPipelineSettings.tag_size)
                    ),
                    fx=self.cameraMatrix[0][0],
                    fy=self.cameraMatrix[1][1],
                    cx=self.cameraMatrix[0][2],
                    cy=self.cameraMatrix[1][2],
                )
            )
        )

        self.distCoeffs = self.getDistCoeffs(cameraIndex)

        self.camera_transform: Optional[Transform3d] = self.getCameraTransform(
            cameraIndex
        )

    @lru_cache(maxsize=100)
    def estimateTagPose(
        self, tag: apriltag.AprilTagDetection
    ) -> apriltag.AprilTagPoseEstimate:
        return self.poseEstimator.estimateOrthogonalIteration(detection=tag, nIters=10)

    def processFrame(self, img, timestamp: float) -> FrameResult:
        # Convert image to grayscale for detection
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        tagSize = self.getSetting(ApriltagPipelineSettings.tag_size)

        tags = self.apriltagDetector.detect(gray)
        results: List[ApriltagResult] = []

        if not tags:
            self.setDataValue("hasResults", False)
            self.setDataValue("results", ApriltagsJson.empty())
            return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

        for tag in tags:
            if tag.getId() < 0 or tag.getId() > max(self.fmap.fieldMap.keys()):
                return gray
            tagPoseEstimate: apriltag.AprilTagPoseEstimate = self.estimateTagPose(tag)

            tagRelativePose: Transform3d = (
                tagPoseEstimate.pose1
            )  # TODO: check if needs to switch with pose2 sometimes

            if tagSize:
                self.drawTagDetectionMarker(
                    tag=tag,
                    tagTransform=tagRelativePose,
                    tagSize=tagSize,
                    img=gray,
                )

            tagRelativePose = self.opencvToWPI(tagRelativePose)

            # if self.getSetting(ApriltagPipeline.kStickToGroundKey):
            #     tagRelativePose = Transform3d(
            #         tagRelativePose.translation(),
            #         Rotation3d(
            #             0,
            #             0,
            #             tagRelativePose.rotation().Z(),
            #         ),
            #     )

            self.setDataValue(
                self.kTagPoseEstimateKey,
                [
                    tagRelativePose.translation().X(),
                    tagRelativePose.translation().Y(),
                    tagRelativePose.translation().Z(),
                    tagRelativePose.rotation().x_degrees,
                    tagRelativePose.rotation().y_degrees,
                    tagRelativePose.rotation().z_degrees,
                ],
            )

            if (
                self.getSetting(ApriltagPipelineSettings.fieldpose)
                and self.camera_transform
            ):
                tagFieldPose = ApriltagPipeline.getTagPoseOnField(tag.getId())

                if tagFieldPose:
                    robotPoseEstimate = ApriltagPipeline.tagToRobotPose(
                        tagFieldPose=tagFieldPose,
                        cameraToRobotTransform=self.camera_transform,
                        cameraToTagTransform=Transform3d(
                            translation=tagRelativePose.translation(),
                            rotation=tagRelativePose.rotation(),
                        ),
                    )

                    self.setDataValue(
                        self.kRobotPoseFieldSpaceKey,
                        [
                            robotPoseEstimate.robotPose_fieldSpace.translation().X(),
                            robotPoseEstimate.robotPose_fieldSpace.translation().Y(),
                            robotPoseEstimate.robotPose_fieldSpace.translation().Z(),
                            robotPoseEstimate.robotPose_fieldSpace.rotation().x_degrees,
                            robotPoseEstimate.robotPose_fieldSpace.rotation().y_degrees,
                            robotPoseEstimate.robotPose_fieldSpace.rotation().z_degrees,
                        ],
                    )

                    results.append(
                        ApriltagResult(
                            detection=tag,
                            timestamp=timestamp,
                            robotPoseEstimate=robotPoseEstimate,
                            tagPoseEstimate=tagPoseEstimate,
                        )
                    )

        self.setDataValue("hasResults", True)
        self.setDataValue(
            "results",
            ApriltagsJson.toJsonString(
                results,
                getIgnoredDataByVerbosity(
                    ApriltagVerbosity.fromValue(
                        self.getSetting(ApriltagPipelineSettings.verbosity)
                    )
                ),
            ),
        )

        return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

    def opencvToWPI(self, opencv: Transform3d) -> Transform3d:
        return Transform3d(  # NOTE: Should be correct
            translation=Translation3d(
                x=opencv.X(),
                y=opencv.Z(),
                z=opencv.Y(),
            ),
            rotation=Rotation3d(
                roll=opencv.rotation().Z(),
                pitch=opencv.rotation().X(),
                yaw=opencv.rotation().Y(),
            ),
        )

    def drawTagDetectionMarker(
        self,
        tag: apriltag.AprilTagDetection,
        tagTransform: Transform3d,
        tagSize: units.meters,
        img: Frame,
    ) -> None:
        if tagSize is not None and tagSize > 0:
            # self.drawPoseBox(
            #     img,
            #     self.cameraMatrix,
            #     self.distCoeffs,
            #     tagTransform,
            #     tagSize,
            # )
            # self.drawPoseAxes(
            #     img,
            #     self.cameraMatrix,
            #     self.distCoeffs,
            #     tagTransform,
            #     np.array([tag.getCenter().x, tag.getCenter().y]),
            #     tagSize,
            # )
            ...

    @staticmethod
    def getTagPoseOnField(id: int) -> Optional[Pose3d]:
        """Retrieve the pose of the AprilTag in the field coordinates."""
        return ApriltagPipeline.fmap.getTagPose(id)

    @staticmethod
    def tagToRobotPose(
        tagFieldPose: Pose3d,
        cameraToRobotTransform: Transform3d,
        cameraToTagTransform: Transform3d,
    ) -> RobotPoseEstimate:
        """
        Computes the robot's pose on the field based on the tag's pose in field coordinates.
        It transforms the pose through the camera and robot coordinate systems.
        """
        robotInTagSpace: Transform3d = (
            cameraToTagTransform.inverse() + cameraToRobotTransform
        )
        robotInField: Pose3d = tagFieldPose.transformBy(robotInTagSpace)
        return RobotPoseEstimate(robotInTagSpace, robotInField)

    def getCameraMatrix(self, cameraIndex: CameraID) -> Optional[List[List[float]]]:
        camConfig = GlobalSettings.getCameraConfig(cameraIndex)
        if camConfig:
            calibrationData = camConfig.calibration
            currRes = self.getSetting(self.settings.resolution)
            if currRes in calibrationData:
                lst = calibrationData[currRes].matrix
                matrix = [lst[i : i + 3] for i in range(0, 9, 3)]
                return matrix
            else:
                return None
        else:
            log.err("No camera matrix found, invalid results for AprilTag detection")
        return None

    def getDistCoeffs(self, cameraIndex: CameraID) -> Optional[List[float]]:
        data = GlobalSettings.getCameraConfig(cameraIndex)
        currRes = self.getSetting(self.settings.resolution)
        if data and currRes in data.calibration:
            return data.calibration[currRes].distCoeff
        return None

    def getCameraTransform(self, cameraIndex: CameraID) -> Optional[Transform3d]:
        data = GlobalSettings.getCameraConfig(cameraIndex)
        if data:
            return data.transform
        return None

    @staticmethod
    def drawPoseBox(
        img: MatLike,
        camera_matrix: np.ndarray,
        dcoeffs: np.ndarray,
        pose: geometry.Transform3d,
        tagSize: float,
        z_sign: int = 1,
    ) -> None:
        """
        Draws the 3d pose box around the AprilTag.

        :param img: The image to write on.
        :param camera_matrix: The camera's intrinsic calibration matrix.
        :param pose: The ``Pose3d`` of the tag.
        :param z_sign: The direction of the z-axis.
        """
        # # Creates object points
        # opoints = (
        #     np.array(
        #         [
        #             -1,
        #             -1,
        #             0,
        #             1,
        #             -1,
        #             0,
        #             1,
        #             1,
        #             0,
        #             -1,
        #             1,
        #             0,
        #             -1,
        #             -1,
        #             -2 * z_sign,
        #             1,
        #             -1,
        #             -2 * z_sign,
        #             1,
        #             1,
        #             -2 * z_sign,
        #             -1,
        #             1,
        #             -2 * z_sign,
        #         ]
        #     ).reshape(-1, 1, 3)
        #     * 0.5
        #     * tagSize
        # )
        #
        # # Creates edges
        # edges = np.array(
        #     [0, 1, 1, 2, 2, 3, 3, 0, 0, 4, 1, 5, 2, 6, 3, 7, 4, 5, 5, 6, 6, 7, 7, 4]
        # ).reshape(-1, 2)
        #
        # TODO: fix to not use toVector
        # # Calulcates rotation and translation vectors for each AprilTag
        # rVecs = pose.rotation().toVector()
        # tVecs = pose.translation().toVector()
        #
        # # Calulate image points of each AprilTag
        # ipoints, _ = cv2.projectPoints(opoints, rVecs, tVecs, camera_matrix, dcoeffs)
        # ipoints = np.round(ipoints).astype(int)
        # ipoints = [tuple(pt) for pt in ipoints.reshape(-1, 2)]
        #
        # # Draws lines between all the edges
        # for i, j in edges:
        #     cv2.line(img, ipoints[i], ipoints[j], (0, 255, 0), 4, 16)

    @staticmethod
    def drawPoseAxes(
        img: MatLike,
        camera_matrix: np.ndarray,
        dcoeffs: np.ndarray,
        pose: Transform3d,
        center: Union[cv2.typing.Point, np.ndarray],
        tagSize: float,
    ) -> None:
        """
        Draws the colored pose axes around the AprilTag.

        :param img: The image to write on.
        :param camera_matrix: The camera's intrinsic calibration matrix.
        :param pose: The ``Pose3d`` of the tag.
        :param center: The center of the AprilTag.
        """
        # TODO: fix to not use toVector
        # rVecs = pose.rotation().toVector()
        # tVecs = pose.translation().toVector()
        #
        # # Calculate object points of each AprilTag
        # opoints = (
        #     np.float32([[1, 0, 0], [0, -1, 0], [0, 0, -1]]).reshape(  # pyright: ignore
        #         -1, 3
        #     )
        #     * tagSize
        # )
        #
        # # Calulate image points of each AprilTag
        # ipoints, _ = cv2.projectPoints(opoints, rVecs, tVecs, camera_matrix, dcoeffs)
        # ipoints = np.round(ipoints).astype(int)
        #
        # # Calulates the center
        # center = np.round(center).astype(int)
        # center = tuple(center.ravel())
        #
        # # Draws the 3d pose lines
        # cv2.line(img, center, tuple(ipoints[0].ravel()), (0, 0, 255), 3)
        # cv2.line(img, center, tuple(ipoints[1].ravel()), (0, 255, 0), 3)
        # cv2.line(img, center, tuple(ipoints[2].ravel()), (255, 0, 0), 3)


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


class ApriltagsJson:
    _emptyJson: Optional[str] = None

    @classmethod
    def toJsonString(
        cls, tags: List[ApriltagResult], ignore_keys: Optional[set] = None
    ) -> str:
        ignore_keys = set(
            ignore_keys or []
        )  # Convert ignore_keys to a set for fast lookup
        data: List[dict[str, Any]] = []

        for tag in tags:
            data.append(
                {
                    ApriltagPipeline.kTagIDKey: tag.detection.getId(),
                    ApriltagPipeline.kHammingKey: tag.detection.getHamming(),
                    ApriltagPipeline.kRobotPoseFieldSpaceKey: tag.robotPoseEstimate.robotPose_fieldSpace,
                    ApriltagPipeline.kRobotPoseTagSpaceKey: tag.robotPoseEstimate.robotPose_tagSpace,
                    ApriltagPipeline.kTagPoseEstimateKey: tag.tagPoseEstimate,
                    ApriltagPipeline.kTagCenterKey: [
                        tag.detection.getCenter().x,
                        tag.detection.getCenter().y,
                    ],
                }
            )

        return json.dumps(
            {
                "data": data,
                "type": "apriltag",
            },
            cls=cls.Encoder,
            separators=(",", ":"),
        )

    @classmethod
    def empty(cls) -> str:
        if cls._emptyJson is not None:
            return cls._emptyJson
        else:
            cls._emptyJson = cls.toJsonString([])
            return cls._emptyJson

    class Encoder(json.JSONEncoder):
        def default(self, o):
            if isinstance(o, np.ndarray):
                return o.tolist()  # Convert numpy arrays to lists
            elif isinstance(o, bytes):
                return o.decode()  # Convert bytes to strings
            elif isinstance(o, Pose3d) or isinstance(o, Transform3d):
                return [
                    o.translation().X(),
                    o.translation().Y(),
                    o.translation().Z(),
                    o.rotation().z_degrees,
                    o.rotation().y_degrees,
                    o.rotation().x_degrees,
                ]
            elif isinstance(o, Pose2d):
                return [
                    o.translation().X(),
                    o.translation().Y(),
                    o.rotation().degrees(),
                ]
            elif isinstance(o, apriltag.AprilTagPoseEstimate):
                return {
                    "pose1": o.pose1,
                    "pose2": o.pose2,
                    "error1": o.error1,
                    "error2": o.error2,
                    "ambiguity": o.getAmbiguity(),
                }
            return super().default(o)
