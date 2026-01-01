# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterable, List, Protocol, Sequence, Tuple

import cv2
import numpy as np
from synapse.stypes import Frame
from typing_extensions import Buffer
from wpimath import units
from wpimath.geometry import Pose3d, Rotation3d, Transform3d, Translation3d

Homography = Tuple[float, float, float, float, float, float, float, float, float]
Corners = Tuple[float, float, float, float, float, float, float, float]
Scalar = Sequence[float | int]


@dataclass
class CameraPoseEstimate:
    """Represents a Camera pose estimate in both tag space and field space.

    Attributes:
        cameraPose_tagSpace (Transform3d): The Camera pose relative to the AprilTag (tag space).
        cameraPose_fieldSpace (Pose3d): The Camera pose relative to the field (field space).
    """

    cameraPose_tagSpace: Transform3d
    cameraPose_fieldSpace: Pose3d


def makeCorners(
    x0: float = 0.0,
    y0: float = 0.0,
    x1: float = 0.0,
    y1: float = 0.0,
    x2: float = 0.0,
    y2: float = 0.0,
    x3: float = 0.0,
    y3: float = 0.0,
) -> Corners:
    """Constructs a Corners tuple with 8 float values.

    Args:
        x0 (float, optional): X coordinate of corner 0. Defaults to 0.0.
        y0 (float, optional): Y coordinate of corner 0. Defaults to 0.0.
        x1 (float, optional): X coordinate of corner 1. Defaults to 0.0.
        y1 (float, optional): Y coordinate of corner 1. Defaults to 0.0.
        x2 (float, optional): X coordinate of corner 2. Defaults to 0.0.
        y2 (float, optional): Y coordinate of corner 2. Defaults to 0.0.
        x3 (float, optional): X coordinate of corner 3. Defaults to 0.0.
        y3 (float, optional): Y coordinate of corner 3. Defaults to 0.0.

    Returns:
        Corners: Tuple of 8 floats representing the four (x, y) corners.
    """
    return (x0, y0, x1, y1, x2, y2, x3, y3)


@dataclass(frozen=True)
class AprilTagDetection:
    """Represents the result of an AprilTag detection.

    Attributes:
        tagID (int): Unique identifier of the detected tag.
        homography (Homography): 3x3 homography matrix as a flat tuple.
        hamming (int): Hamming distance for error correction.
        corners (Corners): Flat tuple of 8 floats representing 4 (x, y) corners.
        center (Tuple[int, int]): Center pixel coordinates of the tag.
    """

    tagID: int
    homography: Homography
    hamming: int
    corners: Corners
    center: Tuple[int, int]


@dataclass(frozen=True)
class ApriltagPoseEstimate:
    """Represents an estimated 3D pose of an AprilTag.

    Attributes:
        ambiguity (float): Ambiguity score of the pose estimate.
        error1 (float): Reprojection error for the first pose solution.
        error2 (float): Reprojection error for the second pose solution.
        pose1 (Transform3d): First possible 3D pose of the tag.
        pose2 (Transform3d): Second possible 3D pose of the tag.
    """

    ambiguity: float
    acceptedError: float
    rejectedError: float
    acceptedPose: Transform3d
    rejectedPose: Transform3d


class AprilTagDetector(ABC):
    """Abstract base class for AprilTag detectors."""

    @dataclass
    class Config:
        """Configuration for AprilTag detection.

        Attributes:
            numThreads (int): Number of threads used for detection. Defaults to 1.
            refineEdges (bool): Whether to refine tag edges. Defaults to True.
            quadDecimate (float): Decimation factor for image preprocessing. Defaults to 2.0.
            quadSigma (float): Sigma value for Gaussian blur. Defaults to 0.0.
        """

        numThreads: int = 1
        refineEdges: bool = True
        quadDecimate: float = 2.0
        quadSigma: float = 0.0

    @abstractmethod
    def detect(self, frame: Buffer) -> List[AprilTagDetection]:
        """Detect AprilTags in a given frame.

        Args:
            frame (Buffer): Input image buffer.

        Returns:
            List[AprilTagDetection]: List of detected AprilTags.
        """
        ...

    @abstractmethod
    def setFamily(self, fam: str) -> None:
        """Set the AprilTag family to detect.

        Args:
            fam (str): The tag family name (e.g., "tag36h11").
        """
        ...

    @abstractmethod
    def setConfig(self, config: Config) -> None:
        """Set the detector configuration.

        Args:
            config (Config): Detection configuration.
        """
        ...

    @abstractmethod
    def getConfig(self) -> Config: ...


class ApriltagPoseEstimator(ABC):
    """Abstract base class for AprilTag pose estimators."""

    @dataclass
    class Config:
        """Camera and tag configuration for pose estimation.

        Attributes:
            cx (float): Principal point x-coordinate.
            cy (float): Principal point y-coordinate.
            fx (float): Focal length in x direction.
            fy (float): Focal length in y direction.
            tagSize (units.meters): Physical size of the AprilTag.
        """

        cx: float
        cy: float
        fx: float
        fy: float
        tagSize: units.meters

    @abstractmethod
    def estimate(
        self, tagDetection: AprilTagDetection, nIters: int
    ) -> ApriltagPoseEstimate:
        """Estimate the pose of a detected AprilTag.

        Args:
            tagDetection (AprilTagDetection): Detected AprilTag data.
            nIters (int): Number of iterations for refinement.

        Returns:
            ApriltagPoseEstimate: Estimated 3D pose.
        """
        ...

    @abstractmethod
    def setConfig(self, config: Config) -> None:
        """Set the estimator configuration.

        Args:
            config (Config): Pose estimation configuration.
        """
        ...

    @abstractmethod
    def getConfig(self) -> Config: ...


class ICombinedApriltagCameraPoseEstimator(Protocol):
    @staticmethod
    def estimate(tags: Iterable[CameraPoseEstimate], **kwargs) -> Pose3d: ...


def drawTagDetectionMarker(
    tag: AprilTagDetection,
    img: Frame,
    color: Scalar = (255, 255, 0),
) -> None:
    """Draw a 2D bounding box, center, and ID for an AprilTag on an image.

    Args:
        tag (AprilTagDetection): The AprilTag detection data.
        img (Frame): Image frame on which to draw.
    """
    # Convert flat tuple to 4 (x, y) points
    corners = np.array(tag.corners, dtype=int).reshape(4, 2)

    # Draw the boundary
    for i in range(4):
        pt1 = tuple(corners[i])
        pt2 = tuple(corners[(i + 1) % 4])
        cv2.line(img, pt1, pt2, color=(0, 255, 0), thickness=2)

    # Draw the center
    center_x = int(sum(c[0] for c in corners) / 4)
    center_y = int(sum(c[1] for c in corners) / 4)
    cv2.circle(img, (center_x, center_y), radius=4, color=(0, 0, 255), thickness=-1)

    # Draw the tag ID above the tag
    tag_id = tag.tagID
    cv2.putText(
        img,
        str(tag_id),
        (center_x - 10, center_y - 10),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        color,
        2,
        cv2.LINE_AA,
    )


def tagToCameraPose(
    tagFieldPose: Pose3d,
    cameraToTagTransform: Transform3d,
) -> CameraPoseEstimate:
    """Compute the Camera's pose on the field given a tag's field pose.

    Args:
        tagFieldPose (Pose3d): AprilTag pose in field coordinates.
        cameraToTagTransform (Transform3d): Transform from camera to tag coordinates.

    Returns:
        CameraPoseEstimate: Camera pose in both tag and field spaces.
    """
    cameraInTagSpace = cameraToTagTransform.inverse()
    cameraInField: Pose3d = tagFieldPose.transformBy(cameraInTagSpace)
    return CameraPoseEstimate(cameraInTagSpace, cameraInField)


def opencvToWPI(opencv: Transform3d) -> Transform3d:
    """Convert an OpenCV-style Transform3d to a WPILib-style Transform3d.

    Args:
        opencv (Transform3d): OpenCV-style transform.

    Returns:
        Transform3d: WPILib-compatible transform.
    """
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
