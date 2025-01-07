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
from dt_apriltags import Detector
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
            # Get AprilTag pose relative to the camera
            tag_translation_camera = np.array(tag.pose_t).flatten()
            tag_rotation_camera = np.array(tag.pose_R)

            # Compute the transform matrix for the robot relative to the camera
            robot_transform = np.eye(4)  # identity matrix, (0,0,0) essentialy
            robot_transform[:3, :3] = tag_rotation_camera
            robot_transform[:3, 3] = tag_translation_camera

            # Overlay tag detection details
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

            # Extract translation vector
            translation = robot_transform[:3, 3]
            translation3d = Translation3d(
                translation[2], translation[0], translation[1]
            )

            # Extract rotation matrix and convert to Rotation3d
            rotation_matrix = robot_transform[:3, :3]
            rvec = cv2.Rodrigues(rotation_matrix)[0].flatten()
            rotation3d = Rotation3d(*rvec)

            # cv2.drawFrameAxes(
            #     gray,
            #     self.camera_matrix,
            #     self.distCoeffs,
            #     translation,
            #     np.array(rvec),
            #     0.1,
            # )

            # Create Transform3d
            self.setDataValue(
                "detectionPose",
                [translation3d.X(), translation3d.Y(), translation3d.Z()],
            )
            self.setDataValue(
                "detectionRotation", [rotation3d.X(), rotation3d.Y(), rotation3d.Z()]
            )

            if self.getSetting("fieldpose") and self.camera_transform:
                tagPose = ApriltagPipeline.getTagPoseOnField(tag.tag_id)

                if tagPose:
                    robotPose = ApriltagPipeline.tagToRobotPose(
                        tagFieldPose=tagPose,
                        robotToCameraTransform=self.camera_transform,
                        cameraToTagTransform=Transform3d(
                            translation=translation3d,
                            rotation=rotation3d,
                        ).inverse(),
                    )

                    robotRotation = robotPose.rotation()

                    # Step 2: Translate the robot's position to the tag's origin (centered at the tag)

                    # Step 3: Apply the rotation around the tag (Rotation2d object applies the rotation)
                    rotated_position = translation3d.rotateBy(rotation3d)
                    # Step 4: Translate the rotated position back to the field's coordinate system
                    final_position = tagPose + Transform3d(
                        translation=rotated_position, rotation=Rotation3d()
                    )

                    self.setDataValue(
                        "selfPose",
                        [final_position.X(), final_position.Y(), final_position.Z()],
                    )
                    # self.setDataValue(
                    #     "selfRotation",
                    #     [final_position.X(), final_position.Y(), final_position.Z()],
                    # )

                    # Step 5: Set the robot pose on the field using the adjusted position
                    self.field.setRobotPose(
                        Pose2d(
                            translation=Translation2d(
                                final_position.translation().X(),
                                final_position.translation().Y(),
                            ),
                            rotation=Rotation2d(),
                        )
                    )

                    # self.setDataValue("field", self.field)
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
    def extractRotationFromMatrix(rvec):
        rotation_matrix, _ = cv2.Rodrigues(rvec)
        sy = np.sqrt(rotation_matrix[0, 0] ** 2 + rotation_matrix[1, 0] ** 2)
        singular = sy < 1e-6

        if not singular:
            yaw = np.arctan2(rotation_matrix[2, 1], rotation_matrix[2, 2])
            pitch = np.arctan2(-rotation_matrix[2, 0], sy)
            roll = np.arctan2(rotation_matrix[1, 0], rotation_matrix[0, 0])
        else:
            yaw = np.arctan2(-rotation_matrix[1, 2], rotation_matrix[1, 1])
            pitch = np.arctan2(-rotation_matrix[2, 0], sy)
            roll = 0

        return Rotation3d(roll=roll, pitch=pitch, yaw=yaw)

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
