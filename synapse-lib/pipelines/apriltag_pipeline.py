from typing import Optional
from cv2.typing import MatLike
import numpy as np
from wpilib import Field2d, Timer
from wpimath.geometry import (
    Pose2d,
    Pose3d,
    Rotation2d,
    Transform3d,
    Rotation3d,
    Translation2d,
    Translation3d,
)
from pupil_apriltags import Detector
from synapse.pipeline import GlobalSettings, Pipeline, PipelineSettings
import synapse.log as log
import cv2
from robotpy_apriltag import AprilTagField, AprilTagFieldLayout


class ApriltagPipeline(Pipeline):
    def __init__(self, settings: PipelineSettings, camera_index: int):
        self.settings = settings
        self.camera_matrix = np.array(
            self.getCameraMatrix(camera_index), dtype=np.float32
        )

        self.distCoeffs = np.array(self.getDistCoeffs(camera_index), dtype=np.float32)

        self.camera_transform = self.getCameraTransform(camera_index)

        ApriltagPipeline.fmap = AprilTagFieldLayout()
        ApriltagPipeline.fmap = ApriltagPipeline.fmap.loadField(
            AprilTagField.k2025Reefscape
        )

        self.field = Field2d()
        self.detector = Detector(families="tag36h11")

    def process_frame(self, img, timestamp: float) -> cv2.typing.MatLike:
        # Convert image to grayscale for detection
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Detect AprilTags
        tags = self.detector.detect(
            gray,
            estimate_tag_pose=True,
            camera_params=(
                self.camera_matrix[0][0],  # pyright: ignore  # fx
                self.camera_matrix[1][1],  # pyright: ignore  # fy
                self.camera_matrix[0][2],  # pyright: ignore  # cx
                self.camera_matrix[1][2],  # pyright: ignore  # cy
            ),
            tag_size=self.getSetting("tag_size"),  # pyright: ignore  # Tag size in meters
        )

        gray = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)

        # If no tags are detected, return None
        if not tags:
            return gray

        for tag in tags:  # pyright: ignore
            poseMatrix = np.concatenate([tag.pose_R, tag.pose_t], axis=1)
            pose3d = self.getPose3DFromTagPoseMatrix(poseMatrix)

            self.drawPoseBox(gray, self.camera_matrix, self.distCoeffs, poseMatrix)
            self.drawPoseAxes(
                gray, self.camera_matrix, self.distCoeffs, poseMatrix, tag.center
            )

            self.setDataValue(
                "deltaTagPose",
                [
                    pose3d.translation().X(),
                    pose3d.translation().Y(),
                    pose3d.translation().Z(),
                    pose3d.rotation().X(),
                    pose3d.rotation().Y(),
                    pose3d.rotation().Z(),
                ],
            )

            if self.getSetting("fieldpose") and self.camera_transform:
                tagPose = ApriltagPipeline.getTagPoseOnField(tag.tag_id)

                if tagPose:
                    robotPose = ApriltagPipeline.tagToRobotPose(
                        tagFieldPose=tagPose,
                        robotToCameraTransform=self.camera_transform,
                        cameraToTagTransform=Transform3d(
                            translation=pose3d.translation(),
                            rotation=pose3d.rotation(),
                        ).inverse(),
                    )

                    self.setDataValue(
                        "robotPose",
                        [
                            robotPose.translation().X(),
                            robotPose.translation().Y(),
                            robotPose.translation().Z(),
                            robotPose.rotation().X(),
                            robotPose.rotation().Y(),
                            robotPose.rotation().Z(),
                        ],
                    )

                    self.field.setRobotPose(
                        Pose2d(
                            translation=Translation2d(
                                robotPose.translation().X(),
                                robotPose.translation().Y(),
                            ),
                            rotation=Rotation2d(
                                tagPose.rotation().Z() - pose3d.rotation().Z()
                            ),
                        )
                    )

                    self.setDataValue("timestamp", Timer.getFPGATimestamp())
                    self.setDataValue("field", self.field)
        return gray

    @staticmethod
    def getTagPoseOnField(id: int) -> Optional[Pose3d]:
        """Retrieve the pose of the AprilTag in the field coordinates."""
        return ApriltagPipeline.fmap.getTagPose(id)

    @staticmethod
    def tagToRobotPose(
        tagFieldPose: Pose3d,
        robotToCameraTransform: Transform3d,
        cameraToTagTransform: Transform3d,
    ) -> Pose3d:
        """
        Computes the robot's pose on the field based on the tag's pose in field coordinates.
        It transforms the pose through the camera and robot coordinate systems.
        """
        cameraInField = tagFieldPose.transformBy(
            cameraToTagTransform.inverse()
        )  # Transform tag to camera space
        robotInField = cameraInField.transformBy(
            robotToCameraTransform.inverse()
        )  # Transform camera to robot space

        return robotInField

    def getCameraMatrix(self, camera_index: int) -> Optional[list[list[float]]]:
        camera_configs = ApriltagPipeline.getCameraConfigsGlobalSettings()
        if isinstance(camera_configs, dict):
            return camera_configs.get(camera_index, {})["matrix"]
        log.err("No camera matrix found, invalid results for AprilTag detection")
        return None

    def getDistCoeffs(self, camera_index: int) -> Optional[list[list[float]]]:
        camera_configs = ApriltagPipeline.getCameraConfigsGlobalSettings()
        if isinstance(camera_configs, dict):
            return camera_configs.get(camera_index, {})["distCoeffs"]
        log.err("No camera distCoeffs found, invalid results for AprilTag detection")
        return None

    @staticmethod
    def getCameraConfigsGlobalSettings():
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

    def drawPoseBox(self, img: MatLike, camera_matrix, dcoeffs, pose, z_sign=1):
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
            * (self.getSetting("tag_size"))  # pyright: ignore
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
            tempRot = Rotation3d(
                np.array(
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

    def drawPoseAxes(self, img: MatLike, camera_matrix, dcoeffs, pose, center):
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
        opoints = np.float32([[1, 0, 0], [0, -1, 0], [0, 0, -1]]).reshape(  # pyright: ignore
            -1, 3
        ) * self.getSetting("tag_size")  # pyright: ignore

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
