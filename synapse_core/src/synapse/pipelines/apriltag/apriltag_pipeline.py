# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from dataclasses import dataclass
from enum import Enum
from functools import cache, lru_cache
from typing import Any, Dict, Final, List, Optional, Set

import cv2
import numpy as np
from synapse.core.pipeline import (FrameResult, Pipeline, PipelineSettings,
                                   Setting, SettingsValue, SynapseCamera,
                                   pipelineResult)
from synapse.core.settings_api import (BooleanConstraint, EnumeratedConstraint,
                                       NumberConstraint, settingField)
from synapse.log import warn
from synapse.pipelines.apriltag.apriltag_detector import (
    AprilTagDetection, AprilTagDetector, ApriltagPoseEstimate,
    ApriltagPoseEstimator, ICombinedApriltagRobotPoseEstimator,
    RobotPoseEstimate, drawTagDetectionMarker, opencvToWPI, tagToRobotPose)
from synapse.pipelines.apriltag.apriltag_robotpy import (
    RobotpyApriltagDetector, RobotpyApriltagPoseEstimator)
from synapse.pipelines.apriltag.field_loader import ApriltagFieldJson
from synapse.pipelines.apriltag.multi_tag_estimator import \
    WeightedAverageMultiTagEstimator
from synapse.stypes import CameraID
from wpimath import units
from wpimath.geometry import Pose3d, Transform3d


class ApriltagVerbosity(Enum):
    kPoseOnly = 0
    kTagDetails = 1
    kTagDetectionData = 2
    kAll = 3

    @classmethod
    def fromValue(cls, value: int) -> "ApriltagVerbosity":
        if value == cls.kPoseOnly.value:
            return cls.kPoseOnly
        if value == cls.kTagDetails.value:
            return cls.kTagDetails
        if value == cls.kTagDetectionData.value:
            return cls.kTagDetectionData
        if value == cls.kAll.value:
            return cls.kAll
        warn(f"Unknown apriltag verbosity: {value}, reverting to default (0)")
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


class ApriltagPipelineSettings(PipelineSettings):
    tag_size = settingField(
        NumberConstraint(minValue=0, maxValue=None),
        default=units.meters(0.1651),
        description="Physical size of the AprilTag in meters.",
    )
    tag_family = settingField(
        EnumeratedConstraint(["tag36h11", "tag16h5"]),
        default="tag36h11",
        description="AprilTag family to detect.",
    )
    stick_to_ground = settingField(
        BooleanConstraint(),
        default=False,
        description="If True, the detected pose will be constrained to the ground plane.",
    )
    fieldpose = settingField(
        BooleanConstraint(),
        default=True,
        description="If True, estimate the tag's pose relative to the field coordinate frame.",
    )
    verbosity = settingField(
        EnumeratedConstraint(options=[ver.value for ver in ApriltagVerbosity]),
        default=ApriltagVerbosity.kPoseOnly.value,
        description="Level of logging and debug output.",
    )
    num_threads = settingField(
        NumberConstraint(minValue=1, maxValue=6, step=1),
        default=1,
        description="Number of CPU threads used for AprilTag detection.",
    )
    refine_edges = settingField(
        BooleanConstraint(renderAsButton=False),
        default=True,
        description="If True, perform edge refinement to improve detection accuracy.",
    )
    quad_decimate = settingField(
        NumberConstraint(minValue=0.0, maxValue=None),
        default=2.0,
        description="Decimation factor for the input image to speed up detection.",
    )
    quad_sigma = settingField(
        NumberConstraint(minValue=0.0, maxValue=None),
        default=0.0,
        description="Gaussian blur sigma applied to the input image before detection.",
    )
    iteration_count = settingField(
        NumberConstraint(minValue=1, maxValue=None, step=1),
        default=4,
        description="Number of iterations for pose estimation refinement.",
    )


@dataclass
class ApriltagDetectionResult:
    detection: AprilTagDetection
    timestamp: float
    robotPoseEstimate: RobotPoseEstimate
    tagPoseEstimate: ApriltagPoseEstimate


@pipelineResult
class ApriltagResult:
    robotPoseEstimate: Optional[Pose3d]
    tagDetections: List[ApriltagDetectionResult]


class ApriltagPipeline(Pipeline[ApriltagPipelineSettings, ApriltagResult]):
    kHammingKey: Final[str] = "hamming"
    kTagIDKey: Final[str] = "tag_id"
    kMeasuredMatrixResolutionKey: Final[str] = "measured_res"
    kRobotPoseFieldSpaceKey: Final[str] = "robotPose_fieldSpace"
    kRobotPoseTagSpaceKey: Final[str] = "robotPose_tagSpace"
    kTagPoseEstimateKey: Final[str] = "tag_estimate"
    kTagPoseEstimateErrorKey: Final[str] = "tag_error"
    kTagPoseFieldSpaceKey: Final[str] = "tagPose_fieldSpace"
    kTagCenterKey: Final[str] = "tagPose_screenSpace"
    kRobotPoseEstimateKey: Final[str] = "robotEstimate_fieldSpace"
    kTagDetectionsKey: Final[str] = "tags"

    def __init__(self, settings: ApriltagPipelineSettings):
        super().__init__(settings)
        self.settings: ApriltagPipelineSettings = settings
        self.combinedApriltagPoseEstimator: ICombinedApriltagRobotPoseEstimator = (
            WeightedAverageMultiTagEstimator()
        )
        ApriltagPipeline.fmap = ApriltagFieldJson.loadField("config/fmap.json")

    def bind(self, cameraIndex: CameraID, camera: SynapseCamera):
        super().bind(cameraIndex, camera)
        self.cameraMatrix: List[List[float]] = (
            self.getCameraMatrix(cameraIndex) or np.eye(3).tolist()
        )

        self.distCoeffs = self.getDistCoeffs(cameraIndex)
        self.camera_transform = self.getCameraTransform(cameraIndex)
        self.apriltagDetector: AprilTagDetector = RobotpyApriltagDetector()

        detectorConfig: AprilTagDetector.Config = AprilTagDetector.Config()

        detectorConfig.numThreads = int(self.getSetting(self.settings.num_threads))
        detectorConfig.quadDecimate = self.getSetting(self.settings.quad_decimate)
        detectorConfig.quadSigma = self.getSetting(self.settings.quad_sigma)
        detectorConfig.refineEdges = self.getSetting(self.settings.refine_edges)

        self.apriltagDetector.setConfig(detectorConfig)

        self.apriltagDetector.setFamily(
            self.settings.getSetting(self.settings.tag_family)
        )

        self.poseEstimator: ApriltagPoseEstimator = RobotpyApriltagPoseEstimator(
            config=ApriltagPoseEstimator.Config(
                tagSize=(self.settings.getSetting(ApriltagPipelineSettings.tag_size)),
                fx=self.cameraMatrix[0][0],
                fy=self.cameraMatrix[1][1],
                cx=self.cameraMatrix[0][2],
                cy=self.cameraMatrix[1][2],
            )
        )

        self.distCoeffs = self.getDistCoeffs(cameraIndex)

        self.camera_transform: Optional[Transform3d] = self.getCameraTransform(
            cameraIndex
        )

    def onSettingChanged(self, setting: Setting, value: SettingsValue) -> None:
        if setting.key in [
            self.settings.num_threads.key,
            self.settings.quad_decimate.key,
            self.settings.quad_sigma.key,
            self.settings.tag_family.key,
        ]:
            config = self.apriltagDetector.getConfig()

            config.numThreads = int(self.getSetting(self.settings.num_threads))
            config.quadDecimate = self.getSetting(self.settings.quad_decimate)
            config.quadSigma = self.getSetting(self.settings.quad_sigma)
            config.refineEdges = self.getSetting(self.settings.refine_edges)

            self.apriltagDetector.setConfig(config)

            self.apriltagDetector.setFamily(
                self.settings.getSetting(self.settings.tag_family)
            )
        elif setting.key == self.settings.tag_size.key:
            config = self.poseEstimator.getConfig()
            config.tagSize = value
            self.poseEstimator.setConfig(config)

    @lru_cache(maxsize=100)
    def estimateTagPose(self, tag: AprilTagDetection) -> ApriltagPoseEstimate:
        return self.poseEstimator.estimate(
            tag,
            nIters=int(self.getSetting(self.settings.iteration_count)),
        )

    def processFrame(self, img, timestamp: float) -> FrameResult:
        # Convert image to grayscale for detection
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        tags = self.apriltagDetector.detect(gray)
        tagEstimates: List[ApriltagDetectionResult] = []

        if not tags:
            self.setDataValue("hasResults", False)
            self.setResults(ApriltagResult(None, []))
            return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

        for tag in tags:
            if tag.tagID < 0 or tag.tagID not in self.fmap.fieldMap.keys():
                warn(f"Invalid tagID: {tag.tagID}")
                return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
            tagPoseEstimate: ApriltagPoseEstimate = self.estimateTagPose(tag)

            self.setDataValue(self.kTagIDKey, tag.tagID)

            tagRelativePose: Transform3d = (
                tagPoseEstimate.acceptedPose
            )  # TODO: check if needs to switch with pose2 sometimes

            drawTagDetectionMarker(
                tag=tag,
                img=gray,
            )

            tagRelativePose = opencvToWPI(tagRelativePose)

            self.setDataValue(self.kTagPoseEstimateKey, tagRelativePose)
            self.setDataValue(
                self.kTagPoseEstimateErrorKey, tagPoseEstimate.acceptedError
            )

            if (
                self.getSetting(ApriltagPipelineSettings.fieldpose)
                and self.camera_transform
            ):
                tagFieldPose = self.fmap.getTagPose(tag.tagID)

                if tagFieldPose:
                    robotPoseEstimate = tagToRobotPose(
                        tagFieldPose=tagFieldPose,
                        cameraToRobotTransform=self.camera_transform,
                        cameraToTagTransform=Transform3d(
                            translation=tagRelativePose.translation(),
                            rotation=tagRelativePose.rotation(),
                        ),
                    )

                    self.setDataValue(
                        self.kRobotPoseFieldSpaceKey,
                        robotPoseEstimate.robotPose_fieldSpace,
                    )

                    tagEstimates.append(
                        ApriltagDetectionResult(
                            detection=tag,
                            timestamp=timestamp,
                            robotPoseEstimate=robotPoseEstimate,
                            tagPoseEstimate=tagPoseEstimate,
                        )
                    )

        self.setDataValue("hasResults", True)
        self.setResults(
            ApriltagsJson.toJsonString(
                ApriltagResult(
                    self.combinedApriltagPoseEstimator.estimate(
                        map(
                            lambda estimate: estimate.robotPoseEstimate,
                            tagEstimates,
                        )
                    ),
                    tagEstimates,
                ),
            ),
        )

        return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


class ApriltagsJson:
    @classmethod
    def toJsonString(cls, result: ApriltagResult) -> Dict[str, Any]:
        tags: List[dict] = []

        for tag in result.tagDetections:
            tag: ApriltagDetectionResult = tag
            tags.append(
                {
                    ApriltagPipeline.kTagIDKey: tag.detection.tagID,
                    ApriltagPipeline.kHammingKey: tag.detection.hamming,
                    ApriltagPipeline.kRobotPoseFieldSpaceKey: tag.robotPoseEstimate.robotPose_fieldSpace,
                    ApriltagPipeline.kTagPoseEstimateKey: tag.tagPoseEstimate,
                    ApriltagPipeline.kTagCenterKey: tag.detection.center,
                }
            )

        return {
            ApriltagPipeline.kRobotPoseEstimateKey: result.robotPoseEstimate,
            ApriltagPipeline.kTagDetectionsKey: tags,
        }

    @classmethod
    def empty(cls) -> List[Dict[str, Any]]:
        return []
