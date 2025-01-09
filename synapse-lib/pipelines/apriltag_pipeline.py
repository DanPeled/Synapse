from typing import Optional
import numpy as np
from wpilib import Field2d
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
            AprilTagField.k2024Crescendo
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

        # If no tags are detected, return None
        if not tags:
            return gray

        for tag in tags:  # pyright: ignore
            corners = tag.corners.astype(int)
            for i in range(4):
                cv2.line(
                    gray,
                    tuple(corners[i]),
                    tuple(corners[(i + 1) % 4]),
                    (0, 255, 0),
                    2,
                )
            center = tuple(tag.center.astype(int))
            cv2.circle(gray, center, 5, (0, 0, 255), -1)

            poseMatrix = np.concatenate([tag.pose_R, tag.pose_t], axis=1)
            pose3d = self.getPose3D(poseMatrix)

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

    def getPose3D(self, poseMatrix=None):
        """
        Calculates a WPILib ``Pose3d`` from the PupilApriltags matrix.

        :param poseMatrix: A 3x4 ``numpy.ndarray``.
        :return: A ``Pose3d`` object.
        """
        # Variables
        x, y, z = 0, 0, 0

        # Extract the tag data from the detection results
        if poseMatrix is not None:
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
        else:
            # Returns a blank Pose3d
            return Pose3d()
