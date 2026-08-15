# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from dataclasses import dataclass
from enum import Enum
from functools import cache
from typing import Any, Dict, Final, List, Optional, Set, cast

import cv2
import numpy as np
from synapse.core.pipeline import (FrameResult, Pipeline, PipelineSettings,
                                   Setting, SettingsValue, SynapseCamera,
                                   pipelineResult)
from synapse.core.settings_api import (BooleanConstraint, EnumeratedConstraint,
                                       NumberConstraint, RangeConstraint,
                                       settingField)
from synapse.hardware.deploy_dir import DeployDirectory
from synapse.hardware.metrics import Platform
from synapse.log import warn
from synapse.pipelines.apriltag.apriltag_detector import (
    AprilTagDetection, AprilTagDetector, ApriltagPoseEstimate,
    ApriltagPoseEstimator, CameraPoseEstimate,
    ICombinedApriltagCameraPoseEstimator, drawTagDetectionMarker,
    tagToCameraPose)
from synapse.pipelines.apriltag.apriltag_robotpy import (
    RobotpyApriltagDetector, RobotpyApriltagPoseEstimator)
from synapse.pipelines.apriltag.field_loader import ApriltagFieldJson
from synapse.pipelines.apriltag.multi_tag_estimator import \
    WeightedAverageMultiTagEstimator
from synapse.stypes import CameraID
from typing_extensions import Buffer
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
    # ==================== Target ====================

    tag_size = settingField(
        NumberConstraint(minValue=0, maxValue=None),
        default=units.meters(0.1651),
        description="Physical size of the AprilTag in meters.",
        category="<Toolbox/> Target",
    )
    tag_family = settingField(
        EnumeratedConstraint(["tag36h11", "tag16h5"]),
        default="tag36h11",
        description="AprilTag family to detect.",
        category="<Toolbox/> Target",
    )

    # ==================== Detection ====================

    num_threads = settingField(
        NumberConstraint(minValue=1, maxValue=Platform.getThreadCount(), step=1),
        default=1,
        description="Number of CPU threads used for AprilTag detection.",
        category="<Toolbox/> Detection",
    )
    refine_edges = settingField(
        BooleanConstraint(renderAsButton=False),
        default=False,
        description="If True, perform edge refinement to improve detection accuracy.",
        category="<Toolbox/> Detection",
    )
    quad_decimate = settingField(
        NumberConstraint(minValue=1.0, maxValue=None),
        default=1.0,
        description="Decimation factor for the input image to speed up detection.",
        category="<Toolbox/> Detection",
    )
    quad_sigma = settingField(
        NumberConstraint(minValue=0.0, maxValue=None),
        default=0.0,
        description="Gaussian blur sigma applied to the input image before detection.",
        category="<Toolbox/> Detection",
    )
    min_cluster_pixels = settingField(
        NumberConstraint(minValue=1, maxValue=None, step=1),
        default=300,
        category="<Toolbox/> Detection",
    )
    max_num_maxima = settingField(
        NumberConstraint(minValue=1, maxValue=None, step=1),
        default=10,
        category="<Toolbox/> Detection",
    )
    critical_angle = settingField(
        NumberConstraint(minValue=0, maxValue=90),
        default=45,
        category="<Toolbox/> Detection",
    )
    max_line_fit_mse = settingField(
        NumberConstraint(minValue=0, maxValue=None),
        default=10,
        category="<Toolbox/> Detection",
    )
    min_white_black_diff = settingField(
        NumberConstraint(minValue=0, maxValue=255, step=1),
        default=5,
        category="<Toolbox/> Detection",
    )
    deglitch = settingField(
        BooleanConstraint(renderAsButton=False),
        default=False,
        category="<Toolbox/> Detection",
    )

    # ==================== Filtering ====================

    crop_x = settingField(
        RangeConstraint(minValue=-1, maxValue=1, step=0.01),
        default=[-1, 1],
        category="<Funnel/> Filtering",
    )
    crop_y = settingField(
        RangeConstraint(minValue=-1, maxValue=1, step=0.01),
        default=[-1, 1],
        category="<Funnel/> Filtering",
    )

    # ==================== Results ====================

    iteration_count = settingField(
        NumberConstraint(minValue=1, maxValue=None, step=1),
        default=4,
        description="Number of iterations for pose estimation refinement.",
        category="<Activity/> Results",
    )
    stick_to_ground = settingField(
        BooleanConstraint(),
        default=False,
        description="If True, the detected pose will be constrained to the ground plane.",
        category="<Activity/> Results",
    )
    publish_camera_field_pose = settingField(
        BooleanConstraint(),
        default=True,
        description="If True, estimate the camera's pose relative to the field coordinate frame.",
        category="<Activity/> Results",
    )
    publish_tag_pose_3d = settingField(
        BooleanConstraint(),
        default=False,
        category="<Activity/> Results",
    )
    verbosity = settingField(
        EnumeratedConstraint.fromEnum(ApriltagVerbosity),
        default=ApriltagVerbosity.kPoseOnly.value,
        description="Level of logging and debug output.",
        category="<Activity/> Results",
    )


@dataclass
class ApriltagDetectionResult:
    detection: AprilTagDetection
    timestamp: float
    cameraPoseEstimate: CameraPoseEstimate
    tagPoseEstimate: ApriltagPoseEstimate


@pipelineResult
class ApriltagResult:
    cameraPoseEstimate: Optional[Pose3d]
    tagDetections: List[ApriltagDetectionResult]


class ApriltagPipeline(Pipeline[ApriltagPipelineSettings, ApriltagResult]):
    kHammingKey: Final[str] = "hamming"
    kTagIDKey: Final[str] = "tag_id"
    kMeasuredMatrixResolutionKey: Final[str] = "measured_res"
    kCameraPoseFieldSpaceKey: Final[str] = "cameraPose_fieldSpace"
    kCameraPoseTagSpaceKey: Final[str] = "cameraPose_tagSpace"
    kTagPoseEstimateKey: Final[str] = "tag_estimate"
    kTagAmbiguityKey: Final[str] = "ambiguity"
    kTagPoseEstimateErrorKey: Final[str] = "tag_error"
    kTagPoseFieldSpaceKey: Final[str] = "tagPose_fieldSpace"
    kTagCenterKey: Final[str] = "tagPose_screenSpace"
    kCameraPoseEstimateKey: Final[str] = "cameraEstimate_fieldSpace"
    kTagDetectionsKey: Final[str] = "tags"

    def __init__(self, settings: ApriltagPipelineSettings):
        super().__init__(settings)
        self.settings: ApriltagPipelineSettings = settings
        self.cameraMatrix = self.getCameraMatrix(self.cameraIndex) or np.eye(3).tolist()
        self.apriltagDetector: AprilTagDetector = RobotpyApriltagDetector()
        self.combinedApriltagPoseEstimator: ICombinedApriltagCameraPoseEstimator = (
            WeightedAverageMultiTagEstimator()
        )
        self.setDetectorConfig(self.cameraIndex)
        self.apriltagDetector.setFamily(
            self.settings.getSetting(self.settings.tag_family)
        )

        ApriltagPipeline.fmap = ApriltagFieldJson.loadField(
            DeployDirectory.getDir() / "fmap.json"
        )

        self.__hadResults: bool = False
        self.tagEstimates: List[ApriltagDetectionResult] = []

        self.poseEstimator: ApriltagPoseEstimator = RobotpyApriltagPoseEstimator(
            config=ApriltagPoseEstimator.Config(
                tagSize=(self.settings.getSetting(ApriltagPipelineSettings.tag_size)),
                fx=self.cameraMatrix[0][0],
                fy=self.cameraMatrix[1][1],
                cx=self.cameraMatrix[0][2],
                cy=self.cameraMatrix[1][2],
            )
        )

    def setDetectorConfig(self, cameraIndex: CameraID) -> None:
        detectorConfig = self.apriltagDetector.getConfig()

        detectorConfig.numThreads = int(self.getSetting(self.settings.num_threads))
        detectorConfig.quadDecimate = self.getSetting(self.settings.quad_decimate)
        detectorConfig.quadSigma = self.getSetting(self.settings.quad_sigma)
        detectorConfig.refineEdges = self.getSetting(self.settings.refine_edges)
        detectorConfig.deglitch = self.getSetting(self.settings.deglitch)
        detectorConfig.minClusterPixels = int(
            self.getSetting(self.settings.min_cluster_pixels)
        )
        detectorConfig.maxLineFitMSE = self.getSetting(self.settings.max_line_fit_mse)
        detectorConfig.maxNumMaxima = int(self.getSetting(self.settings.max_num_maxima))
        detectorConfig.criticalAngle = self.getSetting(self.settings.critical_angle)
        detectorConfig.minWhiteBlackDiff = int(
            self.getSetting(self.settings.min_white_black_diff)
        )

        self.apriltagDetector.setConfig(detectorConfig)

    def bind(self, cameraIndex: CameraID, camera: SynapseCamera):
        super().bind(cameraIndex, camera)

        self.setDetectorConfig(cameraIndex)
        self.apriltagDetector.setFamily(self.getSetting(self.settings.tag_family))

    def onSettingChanged(self, setting: Setting, value: SettingsValue) -> None:
        if setting.key in [
            self.settings.crop_x,
            self.settings.crop_y,
        ]:
            self.cameraMatrix = (
                self.getCameraMatrix(self.cameraIndex) or np.eye(3).tolist()
            )
            cx = self.cameraMatrix[0][2]
            cy = self.cameraMatrix[1][2]
            config = self.poseEstimator.getConfig()
            h, w = self.getResolution()

            crop_x1 = self.getSetting(self.settings.crop_x)[0]
            crop_y1 = self.getSetting(self.settings.crop_y)[0]

            offset_x = int((crop_x1 + 1) * 0.5 * w)
            offset_y = int((crop_y1 + 1) * 0.5 * h)

            config.cx = cx - offset_x
            config.cy = cy - offset_y
            self.poseEstimator.setConfig(config)
        if setting.key in [
            self.settings.num_threads.key,
            self.settings.quad_decimate.key,
            self.settings.quad_sigma.key,
            self.settings.refine_edges.key,
            self.settings.deglitch.key,
            self.settings.min_cluster_pixels.key,
            self.settings.max_line_fit_mse.key,
            self.settings.max_num_maxima.key,
            self.settings.critical_angle.key,
            self.settings.min_white_black_diff.key,
            self.settings.tag_family.key,
        ]:
            self.setDetectorConfig(self.cameraIndex)
            self.apriltagDetector.setFamily(
                self.settings.getSetting(self.settings.tag_family)
            )
        elif setting.key == self.settings.tag_size.key:
            config = self.poseEstimator.getConfig()
            config.tagSize = value
            self.poseEstimator.setConfig(config)

    def estimateTagPose(
        self, tag: AprilTagDetection, iterationCount: int = 1
    ) -> ApriltagPoseEstimate:
        return self.poseEstimator.estimate(tag, nIters=iterationCount)

    def cropImageToFit(self, img, drawOn):
        h, w = img.shape[:2]

        crop_x = self.getSetting(self.settings.crop_x)
        crop_y = self.getSetting(self.settings.crop_y)

        if (
            crop_x == self.settings.crop_x.defaultValue
            and crop_y == self.settings.crop_y.defaultValue
        ):  # No Crop needed, return original image
            return img

        x1 = min(crop_x)
        x2 = max(crop_x)
        y1 = min(crop_y)
        y2 = max(crop_y)

        x1 = int((x1 + 1) * 0.5 * w)
        x2 = int((x2 + 1) * 0.5 * w)
        y1 = int((y1 + 1) * 0.5 * h)
        y2 = int((y2 + 1) * 0.5 * h)

        # Clamp
        x1 = max(0, min(x1, w))
        x2 = max(0, min(x2, w))
        y1 = max(0, min(y1, h))
        y2 = max(0, min(y2, h))

        # Fix corner ordering
        left = min(x1, x2)
        right = max(x1, x2)
        top = min(y1, y2)
        bottom = max(y1, y2)

        cv2.rectangle(
            drawOn,
            (left, top),
            (right - 1, bottom - 1),
            (0, 255, 0),
            2,
        )

        return img[top:bottom, left:right]

    def processFrame(self, img, timestamp: float) -> FrameResult:
        # Convert image to grayscale for detection
        #
        # TODO: Check equalizing histogram (white and black levels)
        cropped_color = self.cropImageToFit(img, img)
        cropped = cv2.cvtColor(cropped_color, cv2.COLOR_BGR2GRAY)

        if not cropped.flags["C_CONTIGUOUS"]:
            cropped = np.ascontiguousarray(cropped)

        tags = self.apriltagDetector.detect(cast(Buffer, cropped))  # pyright: ignore

        if not tags:
            if self.__hadResults:
                self.__hadResults = False
                self.setDataValue("hasResults", False)
                self.setResults(None)
            return img

        self.__hadResults = tags is not None
        self.tagEstimates.clear()

        fieldposeEnabled = self.getSetting(self.settings.publish_camera_field_pose)
        iterationCount = int(self.getSetting(self.settings.iteration_count))
        estimateTag3DPose = self.getSetting(self.settings.publish_tag_pose_3d)

        for tag in tags:
            self.processTag(
                tag,
                timestamp,
                estimateTag3DPose,
                fieldposeEnabled,
                iterationCount,
            )

            drawTagDetectionMarker(
                tag=tag,
                img=img,
            )

        self.setDataValue("hasResults", True)
        result = ApriltagResult(
            self.combinedApriltagPoseEstimator.estimate(
                [estimate.cameraPoseEstimate for estimate in self.tagEstimates]
            ),
            self.tagEstimates,
        )

        self.setResults(ApriltagsJson.toDict(result))  # TODO: Rate Limit NT

        return img

    def processTag(
        self,
        tag: AprilTagDetection,
        timestamp: float,
        estimateTag3DPose: bool,
        fieldposeEnabled: bool,
        poseEstimationIterationCount: int,
    ) -> None:
        if tag.tagID < 0 or tag.tagID not in self.fmap.fieldMap:
            warn(f"Invalid tagID: {tag.tagID}")
            return

        self.setDataValue(self.kTagIDKey, tag.tagID)

        if estimateTag3DPose or fieldposeEnabled:
            tagPoseEstimate: ApriltagPoseEstimate = self.estimateTagPose(
                tag, poseEstimationIterationCount
            )

            tagRelativePose: Transform3d = (
                tagPoseEstimate.acceptedPose
            )  # TODO: check if needs to switch with pose2 sometimes

            if estimateTag3DPose:
                self.setDataValue(self.kTagPoseEstimateKey, tagRelativePose)
                self.setDataValue(
                    self.kTagPoseEstimateErrorKey, tagPoseEstimate.acceptedError
                )

            if fieldposeEnabled:
                tagFieldPose = self.fmap.getTagPose(tag.tagID)

                if tagFieldPose:
                    cameraPoseEstimate = estimateCameraPose(
                        tagFieldPose, tagRelativePose
                    )
                    self.setDataValue(
                        self.kCameraPoseFieldSpaceKey,
                        cameraPoseEstimate.cameraPose_fieldSpace,
                    )

                    self.tagEstimates.append(
                        ApriltagDetectionResult(
                            detection=tag,
                            timestamp=timestamp,
                            cameraPoseEstimate=cameraPoseEstimate,
                            tagPoseEstimate=tagPoseEstimate,
                        )
                    )


def estimateCameraPose(
    tagFieldPose: Pose3d, tagRelativePose: Transform3d
) -> CameraPoseEstimate:
    return tagToCameraPose(
        tagFieldPose=tagFieldPose,
        cameraToTagTransform=tagRelativePose,
    )


class ApriltagsJson:
    @classmethod
    def toDict(cls, result: ApriltagResult) -> Dict[str, Any]:
        tags: List[dict] = []

        for tag in result.tagDetections:
            tag: ApriltagDetectionResult = tag
            tags.append(  # TODO: Expose settings to choose what values to send
                {
                    ApriltagPipeline.kTagIDKey: tag.detection.tagID,
                    ApriltagPipeline.kHammingKey: tag.detection.hamming,
                    ApriltagPipeline.kTagAmbiguityKey: tag.tagPoseEstimate.ambiguity,
                    ApriltagPipeline.kTagPoseEstimateKey: tag.tagPoseEstimate.acceptedPose,
                    ApriltagPipeline.kTagCenterKey: tag.detection.center,
                }
            )

        return {
            ApriltagPipeline.kCameraPoseEstimateKey: result.cameraPoseEstimate,  # Maybe switch to combining pose on the robot instead?
            ApriltagPipeline.kTagDetectionsKey: tags,
        }

    @classmethod
    def empty(cls) -> List[Dict[str, Any]]:
        return []
