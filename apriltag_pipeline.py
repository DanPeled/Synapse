from typing import Optional
import cv2
from synapse import log
from synapse.pipeline_settings import GlobalSettings, PipelineSettings
from synapse.pipeline import Pipeline
from pupil_apriltags import Detector
import numpy as np
from wpimath.geometry import Pose3d, Transform3d, Translation3d, Rotation3d


class ApriltagPipeline(Pipeline):
    def __init__(self, settings: PipelineSettings, camera_index: int):
        self.detector = Detector(
            families="tag36h11",
            nthreads=4,
            quad_decimate=1.0,
            quad_sigma=0.0,
            refine_edges=1,
        )

        self.settings = settings
        self.camera_matrix = self.getCameraMatrix(camera_index)
        self.camera_transform = self.getCameraTransform(camera_index)

    def process_frame(self, img, timestamp: float) -> cv2.typing.MatLike | None:
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
            tag_size=0.1651,  # pyright: ignore  # Tag size in meters
        )

        # If no tags are detected, return None
        if not tags:
            return gray

        # Process detected tags
        robot_transforms = []

        for tag in tags:  # pyright: ignore
            # Get AprilTag pose relative to the camera
            tag_translation_camera = np.array(tag.pose_t).flatten()
            tag_rotation_camera = np.array(tag.pose_R)

            # Compute the transform matrix for the robot relative to the camera
            robot_transform = np.eye(4)  # identity matrix, (0,0,0) essentialy
            robot_transform[:3, :3] = tag_rotation_camera
            robot_transform[:3, 3] = tag_translation_camera

            robot_transforms.append(robot_transform)

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
            cv2.putText(
                gray,
                f"ID: {tag.tag_id}",
                (center[0], center[1] - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1,
            )

        # Average transforms if multiple tags are detected
        if robot_transforms:
            avg_transform = np.mean(robot_transforms, axis=0)
            # Extract translation vector
            translation = avg_transform[:3, 3]
            translation3d = Translation3d(
                translation[0], translation[1], translation[2]
            )

            # Extract rotation matrix and convert to Rotation3d
            rotation_matrix = avg_transform[:3, :3]
            rotation3d = Rotation3d(*cv2.Rodrigues(rotation_matrix)[0].flatten())

            # Create Transform3d
            self.setValue(
                "tagPose", [translation3d.X(), translation3d.Y(), translation3d.Z()]
            )
            self.setValue(
                "tagRotation", [rotation3d.X(), rotation3d.Y(), rotation3d.Z()]
            )

        return gray

    @staticmethod
    def tagToRobotPose(
        tagFieldPose: Pose3d,
        robotToCameraTransform: Transform3d,
        cameraToTagTransform: Transform3d,
    ) -> Pose3d:
        """
        Computes the robot's pose in the field from the tag's pose in the field, using the camera's position and orientation
        relative to both the robot and the tag.

        Args:
            tagFieldPose (Pose3d): The pose of the tag in the field coordinate system, including position and orientation.
            robotToCameraTransform (Transform3d): The transform that relates the robot's coordinate system to the camera's coordinate system.
            cameraToTagTransform (Transform3d): The transform that relates the camera's coordinate system to the tag's coordinate system.

        Returns:
            Pose3d: The computed pose of the robot in the field coordinate system, including position and orientation.

        Explanation:
            This method uses the following logic:
            1. The tag's pose in the field is transformed into the camera's coordinate system by applying the inverse of `cameraToTagTransform`.
            2. The resulting camera pose in the field is then transformed into the robot's coordinate system by applying the inverse of `robotToCameraTransform`.
            3. The final result is the robot's pose in the field.
        """
        cameraInField = tagFieldPose.transformBy(cameraToTagTransform.inverse())
        robotInField = cameraInField.transformBy(robotToCameraTransform.inverse())

        return robotInField

    def getCameraMatrix(self, camera_index: int) -> Optional[list[list[float]]]:
        mat_lst = GlobalSettings["camera_matrix"]
        camera_matrix = None

        if isinstance(mat_lst, dict):
            camera_matrix = mat_lst[camera_index]
            return camera_matrix
        if camera_matrix is None:
            log.log(
                "ERROR: no camera matrix, will not return valid results for apriltag detections"
            )

    def getCameraTransform(self, camera_index: int) -> Optional[Transform3d]:
        trans_matrix_lst = GlobalSettings["camera_transform"]
        trans_matrix = None

        if isinstance(trans_matrix_lst, dict):
            trans_matrix = trans_matrix_lst.get(camera_index)

        if trans_matrix is None:
            log.log(
                "ERROR: no camera transform, will not return valid results for apriltag detections"
            )
            return None

        trans_lst = trans_matrix[0]
        translation3d = Translation3d(*trans_lst)

        rot_lst = trans_matrix[1]
        rotation3d = Rotation3d.fromDegrees(*rot_lst)

        return Transform3d(translation=translation3d, rotation=rotation3d)
