# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache
from typing import Final, Iterable, List, Optional, Sequence, Tuple

import cv2
import numpy as np
from synapse.stypes import Frame
from typing_extensions import Buffer
from wpimath import Pose3d, Rotation3d, Transform3d, Translation3d

Homography = Tuple[float, float, float, float, float, float, float, float, float]
Corners = Tuple[float, float, float, float, float, float, float, float]
Scalar = Sequence[float | int]
Color = Tuple[int, int, int]

TAG_BORDER_RED: Final[Color] = (0, 0, 255)
TAG_BORDER_GREEN: Final[Color] = (0, 255, 0)
TAG_ID_BLUE: Final[Color] = (255, 0, 0)


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


@dataclass(frozen=True, slots=True)
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


@dataclass(frozen=True, slots=True)
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
        minClusterPixels: int = 300
        maxNumMaxima: int = 10
        criticalAngle: float = math.radians(45)
        minWhiteBlackDiff: int = 3
        maxLineFitMSE: float = 10.0
        deglitch: bool = False

        # Detector-specific tuning. Backends that do not support a parameter
        # ignore it. These defaults match NAPA's own defaults.
        minTagPx: int = 32
        maxHamming: Optional[int] = None
        minContrast: int = 20
        minBorderCells: int = 22
        sharpening: float = 0.25
        maxDetections: int = 64

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

    def close(self) -> None:
        """Release any resources held by the detector.

        Detectors that do not own native resources can leave this as a no-op.
        """
        pass


def _tagBorderPoints(tag: AprilTagDetection) -> np.ndarray:
    """Return the four tag corners as one contiguous OpenCV polygon."""
    corners = tag.corners
    points = np.empty((4, 2), dtype=np.int32)
    points[0, 0], points[0, 1] = round(corners[0]), round(corners[1])
    points[1, 0], points[1, 1] = round(corners[2]), round(corners[3])
    points[2, 0], points[2, 1] = round(corners[4]), round(corners[5])
    points[3, 0], points[3, 1] = round(corners[6]), round(corners[7])
    return points


def drawTagBorders(
    img: Frame,
    tags: Iterable[AprilTagDetection],
    color: Scalar = TAG_BORDER_GREEN,
    thickness: int = 2,
) -> None:
    """Draw all tag borders with one OpenCV call."""
    contours = [_tagBorderPoints(tag) for tag in tags]
    if contours:
        cv2.polylines(img, contours, True, color, thickness)


def drawTagIds(
    img: Frame,
    tags: Iterable[AprilTagDetection],
    color: Scalar = TAG_ID_BLUE,
) -> None:
    """Draw each tag's ID in blue over the tag center by default."""
    for tag in tags:
        centerX, centerY = tag.center
        cv2.putText(
            img,
            str(tag.tagID),
            (int(centerX) - 8, int(centerY) + 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            2,
            cv2.LINE_AA,
        )


@lru_cache(maxsize=32)
def poseCubeObjectPoints(tagSize: float) -> np.ndarray:
    """Return cached OpenCV object points for a cube anchored at a tag.

    WPILib tag poses use +X as the tag normal, with the face spanning Y and Z.
    The returned points extend along that normal, and are converted to OpenCV's
    object-point axes so they can be passed directly to ``projectPoints``.
    """
    halfSize = tagSize * 0.5
    wpilibPoints = np.array(
        [
            (0.0, halfSize, -halfSize),
            (0.0, -halfSize, -halfSize),
            (0.0, -halfSize, halfSize),
            (0.0, halfSize, halfSize),
            (tagSize, halfSize, -halfSize),
            (tagSize, -halfSize, -halfSize),
            (tagSize, -halfSize, halfSize),
            (tagSize, halfSize, halfSize),
        ],
        dtype=np.float64,
    )
    return np.ascontiguousarray(
        np.column_stack(
            (-wpilibPoints[:, 1], -wpilibPoints[:, 2], wpilibPoints[:, 0])
        )
    )


def drawTagPoseCube(
    img: Frame,
    tag: AprilTagDetection,
    tagSize: float,
    cameraMatrix: np.ndarray,
    distCoeffs: np.ndarray,
) -> None:
    """Draw a cube anchored to the detected tag and its observed normal.

    The tag homography is decomposed with the camera matrix to recover the tag
    axes in camera space. That keeps the cube attached to the detected corners
    even when the field-pose estimate is unavailable or imperfect.
    """
    localPoints = poseCubeObjectPoints(float(tagSize))
    facePoints = localPoints[:4, :2]
    observed = np.array(_tagBorderPoints(tag), dtype=np.float32)

    if np.any(distCoeffs):
        observed = cv2.undistortPoints(
            observed.reshape(4, 1, 2), cameraMatrix, distCoeffs, P=cameraMatrix
        ).reshape(4, 2)

    homography = cv2.getPerspectiveTransform(
        facePoints.astype(np.float32), observed.astype(np.float32)
    )
    inverseCameraMatrix = np.linalg.inv(cameraMatrix)
    cameraColumns = [inverseCameraMatrix @ homography[:, index] for index in range(3)]
    scale = (np.linalg.norm(cameraColumns[0]) + np.linalg.norm(cameraColumns[1])) * 0.5
    if scale <= 0.0:
        return

    axisX = cameraColumns[0] / scale
    axisY = cameraColumns[1] / scale
    translation = cameraColumns[2] / scale
    # Cross(axisX, axisY) is the tag's OpenCV +Z, i.e. WPILib's tag normal.
    axisNormal = np.cross(axisX, axisY)

    basePoints = (
        axisX * facePoints[:, 0:1]
        + axisY * facePoints[:, 1:2]
        + translation[None, :]
    )
    cubePoints = np.concatenate(
        (basePoints, basePoints + float(tagSize) * axisNormal[None, :]), axis=0
    )

    if np.any(distCoeffs):
        projected, _ = cv2.projectPoints(
            cubePoints, np.zeros(3), np.zeros(3), cameraMatrix, distCoeffs
        )
        farPoints = projected.reshape(8, 2)[4:].round().astype(np.int32)
    else:
        homogeneous = (cameraMatrix @ cubePoints.T).T
        pixels = homogeneous[:, :2] / homogeneous[:, 2:3]
        farPoints = pixels[4:].round().astype(np.int32)

    # The base uses the detected corners directly, so it always aligns with the
    # green border. One call draws the far face and all four connecting edges.
    basePixels = _tagBorderPoints(tag)
    contours = [basePixels, farPoints]
    for index in range(4):
        contours.append(
            np.array((basePixels[index], farPoints[index]), dtype=np.int32)
        )
    cv2.polylines(img, contours, True, TAG_BORDER_GREEN, 2)


def drawTagDetectionOverlays(
    img: Frame,
    tags: Iterable[AprilTagDetection],
    processedTags: Iterable[AprilTagDetection],
    drawCubes: bool,
    tagSize: float,
    cameraMatrix: np.ndarray,
    distCoeffs: np.ndarray,
) -> None:
    """Draw color-coded tag borders, IDs, and 3D cubes for processed tags.

    Red borders mark detections excluded by the tag filter or missing a field
    pose. Green borders mark detections with a usable field pose. Cubes are
    only drawn when ``drawCubes`` is true, which the caller ties to a completed
    3D pose step.
    """
    allTags = list(tags)
    usableTags = list(processedTags)
    usableIds = {tag.tagID for tag in usableTags}
    rejectedTags = [tag for tag in allTags if tag.tagID not in usableIds]

    if drawCubes:
        for tag in usableTags:
            drawTagPoseCube(img, tag, tagSize, cameraMatrix, distCoeffs)

    drawTagBorders(img, rejectedTags, TAG_BORDER_RED)
    drawTagBorders(img, usableTags, TAG_BORDER_GREEN)
    drawTagIds(img, allTags)


def drawTagDetectionMarker(
    tag: AprilTagDetection,
    img: Frame,
    color: Scalar = (255, 255, 0),
) -> None:
    """Draw a standalone 2D border, center, and ID for an AprilTag."""
    drawTagBorders(img, (tag,), TAG_BORDER_GREEN)

    corners = tag.corners
    centerX = int((corners[0] + corners[2] + corners[4] + corners[6]) / 4)
    centerY = int((corners[1] + corners[3] + corners[5] + corners[7]) / 4)
    cv2.circle(img, (centerX, centerY), radius=4, color=TAG_BORDER_RED, thickness=-1)

    drawTagIds(img, (tag,), color)


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


@dataclass
class CameraPoseEstimate:
    """Estimated camera pose in field coordinates."""

    reprojectionError: float
    cameraPoseEstimate: Pose3d
