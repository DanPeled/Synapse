import json
from dataclasses import dataclass
from typing import Any, Dict, Final, List, Optional, Union

import cv2
import numpy as np
from cv2.typing import MatLike
from pupil_apriltags import Detector
from wpimath.geometry import (Pose2d, Pose3d, Quaternion, Rotation2d,
                              Rotation3d, Transform3d, Translation2d,
                              Translation3d)

import core.log as log
from core.pipeline import GlobalSettings, Pipeline, PipelineSettings
from core.stypes import Frame


@dataclass
class RobotPoseEstimate:
    robotPose_tagSpace: Transform3d
    robotPose_fieldSpace: Pose3d


class ApriltagPipeline(Pipeline):
    kTagSizeKey: Final[str] = "tag_size"
    kTagFamily: Final[str] = "tag36h11"
    kGetFieldPoseKey: Final[str] = "fieldpose"
    kStickToGroundKey: Final[str] = "stick_to_ground"
    kMatrixKey: Final[str] = "matrix"
    kMeasuredMatrixResolutionKey: Final[str] = "measured_res"
    kRobotPoseFieldSpaceKey: Final[str] = "robotPose_fieldSpace"
    kRobotPoseTagSpaceKey: Final[str] = "robotPose_tagSpace"
    kCameraPoseTagSpace: Final[str] = "cameraPose_tagSpace"
    kTagPoseFieldSpace: Final[str] = "tagPose_fieldSpace"

    def __init__(self, settings: PipelineSettings, camera_index: int):
        super().__init__(settings, camera_index)
        self.settings = settings
        self.camera_matrix = np.array(
            self.getCameraMatrix(camera_index), dtype=np.float32
        )

        self.distCoeffs = np.array(self.getDistCoeffs(camera_index), dtype=np.float32)
        self.camera_transform = self.getCameraTransform(camera_index)
        self.detector = Detector(families=ApriltagPipeline.kTagFamily, nthreads=4)

        ApriltagPipeline.fmap = ApriltagFieldJson.loadField("config/fmap.json")

    def process_frame(self, img, timestamp: float) -> Frame:
        # Convert image to grayscale for detection
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        tagSize = self.getSetting(self.kTagSizeKey)

        # Detect AprilTags
        tags = self.detector.detect(
            gray,
            estimate_tag_pose=True,
            camera_params=(
                self.camera_matrix[0][0],  # fx
                self.camera_matrix[1][1],  # fy
                self.camera_matrix[0][2],  # cx
                self.camera_matrix[1][2],  # cy
            ),
            tag_size=tagSize,  # Tag size in meters
        )

        gray = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)

        if not tags:
            self.setDataValue("hasResults", False)
            self.setDataValue("results", ApriltagsJson.empty())
            return gray

        for tag in tags:  # pyright: ignore
            poseMatrix = np.concatenate([tag.pose_R, tag.pose_t], axis=1)
            tagRelativePose = self.getPose3DFromTagPoseMatrix(poseMatrix)

            if self.getSetting(ApriltagPipeline.kStickToGroundKey):
                tagRelativePose = Pose3d(
                    tagRelativePose.translation(),
                    Rotation3d(
                        0,
                        0,
                        tagRelativePose.rotation().Z(),
                    ),
                )

            if tagSize is not None and tagSize > 0:
                self.drawPoseBox(
                    gray,
                    self.camera_matrix,
                    self.distCoeffs,
                    poseMatrix,
                    tagSize,
                )
                self.drawPoseAxes(
                    gray,
                    self.camera_matrix,
                    self.distCoeffs,
                    poseMatrix,
                    tag.center,
                    tagSize,
                )

            self.setDataValue(
                self.kCameraPoseTagSpace,
                [
                    tagRelativePose.translation().X(),
                    tagRelativePose.translation().Y(),
                    tagRelativePose.translation().Z(),
                    tagRelativePose.rotation().x_degrees,
                    tagRelativePose.rotation().y_degrees,
                    tagRelativePose.rotation().z_degrees,
                ],
            )

            if self.getSetting(self.kGetFieldPoseKey) and self.camera_transform:
                tagFieldPose = ApriltagPipeline.getTagPoseOnField(tag.tag_id)

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

                    setattr(tag, "timestamp", timestamp)
                    setattr(
                        tag,
                        self.kRobotPoseFieldSpaceKey,
                        robotPoseEstimate.robotPose_fieldSpace,
                    )
                    setattr(
                        tag,
                        self.kRobotPoseTagSpaceKey,
                        robotPoseEstimate.robotPose_tagSpace,
                    )
                    # setattr(tag, self.kTagPoseFieldSpace, tagFieldPose)
                    setattr(tag, self.kCameraPoseTagSpace, tagRelativePose)

        self.setDataValue("hasResults", True)
        self.setDataValue("results", ApriltagsJson.toJsonString(tags))

        return gray

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

    def getCameraMatrix(self, camera_index: int) -> Optional[List[List[float]]]:
        camera_configs = ApriltagPipeline.getCameraConfigsGlobalSettings()

        if isinstance(camera_configs, dict):
            cam_config = camera_configs.get(camera_index, {})
            measured_res = cam_config.get(ApriltagPipeline.kMeasuredMatrixResolutionKey)
            current_res = (self.getSetting("width"), self.getSetting("height"))

            if (
                ApriltagPipeline.kMatrixKey in cam_config
                and measured_res
                and current_res
            ):
                if measured_res != current_res:
                    scale_x = current_res[0] / measured_res[0]
                    scale_y = current_res[1] / measured_res[1]

                    matrix = cam_config[ApriltagPipeline.kMatrixKey]

                    scaled_matrix = [
                        [matrix[0][0] * scale_x, matrix[0][1], matrix[0][2] * scale_x],
                        [matrix[1][0], matrix[1][1] * scale_y, matrix[1][2] * scale_y],
                        [matrix[2][0], matrix[2][1], matrix[2][2]],
                    ]

                    return scaled_matrix

                return cam_config[ApriltagPipeline.kMatrixKey]

        log.err("No camera matrix found, invalid results for AprilTag detection")
        return None

    def getDistCoeffs(self, camera_index: int) -> Optional[List[List[float]]]:
        camera_configs = ApriltagPipeline.getCameraConfigsGlobalSettings()
        if isinstance(camera_configs, dict):
            return camera_configs.get(camera_index, {})["distCoeffs"]
        log.err("No camera distCoeffs found, invalid results for AprilTag detection")
        return None

    @staticmethod
    def getCameraConfigsGlobalSettings() -> Any:
        return GlobalSettings["camera_configs"]

    def getCameraTransform(self, camera_index: int) -> Optional[Transform3d]:
        camera_configs = ApriltagPipeline.getCameraConfigsGlobalSettings()
        trans_matrix = None

        if isinstance(camera_configs, dict):
            trans_matrix = camera_configs[camera_index]["transform"]

        if trans_matrix is None:
            log.err(
                "no camera transform, will not return valid results for apriltag detections"
            )
            return None

        trans_lst = trans_matrix[0]
        translation3d = Translation3d(*trans_lst)
        rot_lst = trans_matrix[1]
        rotation3d = Rotation3d.fromDegrees(*rot_lst)
        return Transform3d(translation=translation3d, rotation=rotation3d)

    @staticmethod
    def drawPoseBox(
        img: MatLike,
        camera_matrix: np.ndarray,
        dcoeffs: np.ndarray,
        pose: np.ndarray,
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
        # Creates object points
        opoints = (
            np.array(
                [
                    -1,
                    -1,
                    0,
                    1,
                    -1,
                    0,
                    1,
                    1,
                    0,
                    -1,
                    1,
                    0,
                    -1,
                    -1,
                    -2 * z_sign,
                    1,
                    -1,
                    -2 * z_sign,
                    1,
                    1,
                    -2 * z_sign,
                    -1,
                    1,
                    -2 * z_sign,
                ]
            ).reshape(-1, 1, 3)
            * 0.5
            * tagSize
        )

        # Creates edges
        edges = np.array(
            [0, 1, 1, 2, 2, 3, 3, 0, 0, 4, 1, 5, 2, 6, 3, 7, 4, 5, 5, 6, 6, 7, 7, 4]
        ).reshape(-1, 2)

        # Calulcates rotation and translation vectors for each AprilTag
        rVecs, _ = cv2.Rodrigues(pose[:3, :3])
        tVecs = pose[:3, 3:]

        # Calulate image points of each AprilTag
        ipoints, _ = cv2.projectPoints(opoints, rVecs, tVecs, camera_matrix, dcoeffs)
        ipoints = np.round(ipoints).astype(int)
        ipoints = [tuple(pt) for pt in ipoints.reshape(-1, 2)]

        # Draws lines between all the edges
        for i, j in edges:
            cv2.line(img, ipoints[i], ipoints[j], (0, 255, 0), 4, 16)

    @staticmethod
    def getPose3DFromTagPoseMatrix(poseMatrix: np.ndarray) -> Pose3d:
        """
        Calculates a WPILib ``Pose3d`` from the PupilApriltags matrix.

        :param poseMatrix: A 3x4 ``numpy.ndarray``.
        :return: A ``Pose3d`` object.
        """
        x, y, z = 0, 0, 0
        # Flattens the pose matrix into a 1D array
        flatPose = np.array(poseMatrix).flatten()

        # Creates the Pose3d components for a tag in the AprilTags WCS
        try:
            tempRot = Rotation3d(  # pyright: ignore
                np.array(  # pyright: ignore
                    [
                        [flatPose[0], flatPose[1], flatPose[2]],
                        [flatPose[4], flatPose[5], flatPose[6]],
                        [flatPose[8], flatPose[9], flatPose[10]],
                    ]
                )
            )
        except ValueError as e:
            tempRot = Rotation3d()
            log.err(f"Error converting array to Rotation3d: {str(e)}")
        tempTrans = Translation3d(flatPose[3], flatPose[7], flatPose[11])

        # Get the camera's measured X, Y, and Z
        tempX = tempTrans.Z()
        y = -tempTrans.X()
        z = -tempTrans.Y()

        # Create a Rotation3d object
        rot = Rotation3d(tempRot.Z(), -tempRot.X(), -tempRot.Y())

        # Calulates the field relative X and Y coordinate
        yTrans = Translation2d(tempX, y).rotateBy(Rotation2d(-rot.Z()))
        x = yTrans.X()
        y = yTrans.Y()

        # Calulates the field relative Z coordinate
        zTrans = Translation2d(tempX, z).rotateBy(Rotation2d(np.pi + rot.Y()))
        z = zTrans.Y()

        # Create a Translation3d object
        trans = Translation3d(x, y, z)

        # Creates a Pose3d object in the field WCS
        pose = Pose3d(trans, rot)

        return pose

    @staticmethod
    def drawPoseAxes(
        img: MatLike,
        camera_matrix: np.ndarray,
        dcoeffs: np.ndarray,
        pose: np.ndarray,
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
        # Calulcates rotation and translation vectors for each AprilTag
        rVecs, _ = cv2.Rodrigues(pose[:3, :3])
        tVecs = pose[:3, 3:]

        # Calculate object points of each AprilTag
        opoints = (
            np.float32([[1, 0, 0], [0, -1, 0], [0, 0, -1]]).reshape(  # pyright: ignore
                -1, 3
            )
            * tagSize
        )

        # Calulate image points of each AprilTag
        ipoints, _ = cv2.projectPoints(opoints, rVecs, tVecs, camera_matrix, dcoeffs)
        ipoints = np.round(ipoints).astype(int)

        # Calulates the center
        center = np.round(center).astype(int)
        center = tuple(center.ravel())

        # Draws the 3d pose lines
        cv2.line(img, center, tuple(ipoints[0].ravel()), (0, 0, 255), 3)
        cv2.line(img, center, tuple(ipoints[1].ravel()), (0, 255, 0), 3)
        cv2.line(img, center, tuple(ipoints[2].ravel()), (255, 0, 0), 3)


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
    def toJsonString(cls, tags) -> str:
        return json.dumps(
            {"data": list(map(lambda tag: tag.__dict__, tags)), "type": "apriltag"},
            cls=ApriltagsJson.Encoder,
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
                return {
                    "x": o.translation().X(),
                    "y": o.translation().Y(),
                    "z": o.translation().Z(),
                    "yaw": o.rotation().z_degrees,
                    "pitch": o.rotation().y_degrees,
                    "roll": o.rotation().x_degrees,
                    "rotation_unit": "degrees",
                }
            elif isinstance(o, Pose2d):
                return {
                    "x": o.translation().X(),
                    "y": o.translation().Y(),
                    "rotation": o.rotation().degrees(),
                    "rotation_unit": "degrees",
                }
            return super().default(o)
