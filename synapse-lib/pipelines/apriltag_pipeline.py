from typing import Optional
from cv2.typing import MatLike
import numpy as np
from wpilib import Field2d
from wpimath.geometry import (
    Pose3d,
    Transform3d,
    Rotation3d,
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

    def process_frame(self, img, timestamp: float) -> MatLike:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        detections = self.detector.detect(
            gray,
            estimate_tag_pose=True,
            camera_params=(
                self.camera_matrix[0, 0],  # fx
                self.camera_matrix[1, 1],  # fy
                self.camera_matrix[0, 2],  # cx
                self.camera_matrix[1, 2],  # cy
            ),
            tag_size=0.1524,
        )
        gray = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)

        for detection in detections:  # pyright: ignore
            tag_id = detection.tag_id
            tag_pose_on_field = self.getTagPoseOnField(tag_id)

            if tag_pose_on_field is None:
                log.err(f"Tag ID {tag_id} not found in the field layout")
                continue

            rvec, _ = cv2.Rodrigues(np.array(detection.pose_R))
            rvec[1, :] *= -1  # Invert Y-axis
            rvec[2, :] *= -1  # Invert Z-axis
            tvec = np.array(detection.pose_t).reshape((3, 1))
            # rotation_matrix = np.array(rvec, dtype=np.float64)
            rotation = ApriltagPipeline.extractRotationFromMatrix(rvec)

            cv2.drawFrameAxes(
                image=gray,
                cameraMatrix=self.camera_matrix,
                distCoeffs=self.distCoeffs,
                rvec=rvec,
                tvec=tvec,
                length=0.1,
            )

            translation = Translation3d(*tvec)

            camera_to_tag_transform = Transform3d(translation, rotation)

            self.setDataValue("TX", tvec[0][0])
            self.setDataValue("TY", tvec[1][0])
            self.setDataValue("TZ", tvec[2][0])

            self.setDataValue("RX", rotation.X())
            self.setDataValue("RY", rotation.Y())
            self.setDataValue("RZ", rotation.Z())

            if self.camera_transform is not None:
                robot_pose = self.tagToRobotPose(
                    tagFieldPose=tag_pose_on_field,
                    robotToCameraTransform=self.camera_transform,
                    cameraToTagTransform=camera_to_tag_transform,
                )
                self.field.setRobotPose(robot_pose.toPose2d())
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
