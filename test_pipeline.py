import json
import robotpy_apriltag as apriltags
import cv2
import wpimath.units as units
from wpilib import Field2d
import math
from synapse.pipeline_settings import PipelineSettings
from synapse.pipeline import Pipeline


class ApriltagPipeline(Pipeline):
    def __init__(self, settings: PipelineSettings):
        self.detector = apriltags.AprilTagDetector()
        self.detector.addFamily("tag36h11")
        self.pose_estimator_config = apriltags.AprilTagPoseEstimator.Config(
            units.meters(0.1651), 1279, 719, 640, 0
        )
        self.pose_estimator = apriltags.AprilTagPoseEstimator(
            self.pose_estimator_config
        )
        with open("config/fmap.json") as fmap:
            self.apmap = json.load(fmap)
        self.field = Field2d()

    @classmethod
    def calculatePoseOnFeild(cls, estimation, tag_id, fmap, z_dis, x_dis):
        tag_transform = None
        for fiducial in fmap["fiducials"]:
            if fiducial["id"] == tag_id:
                tag_transform = fiducial["transform"]
                break

        if tag_transform:
            # ry = math.degrees(math.atan2(tag_transform[0], tag_transform[1])) +90 -estimation.rotation().y_degrees
            ry = math.degrees(math.atan2(tag_transform[0], tag_transform[1])) + 90
            x = (
                (tag_transform[3] + 8.308467)
                + (x_dis * math.sin(math.radians(ry)))
                - (z_dis * math.cos(math.radians(ry)))
            )
            y = (
                (tag_transform[7] + 4.098925)
                + (x_dis * math.cos(math.radians(ry)))
                - (z_dis * math.sin(math.radians(ry)))
            )
            # z = tag_transform[11]
            print(x_dis, math.cos(math.radians(ry)))

            return [x, y, ry]
        else:
            return None

    def process_frame(self, img, timestamp):
        if len(img.shape) == 3:
            img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            img_gray = img

        detections = self.detector.detect(img_gray)
        img_gray = cv2.cvtColor(img_gray, cv2.COLOR_GRAY2RGB)

        for detection in detections:
            center = detection.getCenter()
            estimation = self.pose_estimator.estimate(detection)

            tag_id = detection.getId()

            cv2.putText(
                img_gray,
                f"ID: {tag_id} Estimation: {estimation}",
                (10, 70),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 0),
                2,
            )

            cv2.circle(img_gray, (int(center.x), int(center.y)), 5, (0, 255, 0), -1)

            self.tx = ((center.x / 640) * 111.95855) - 111.95855 / 2
            self.ty = ((-center.y / 480) * 45) + 22.5

            self.setValue("tx", self.tx)
            self.setValue("ty", self.ty)
            self.setValue("cy", center.y)
            self.setValue("TX", estimation.x)
            self.setValue("TY", estimation.y)
            self.setValue("TZ", estimation.z)
            self.setValue("RX", estimation.rotation().x_degrees)
            self.setValue("RY", (estimation.rotation().y_degrees))
            self.setValue("RZ", estimation.rotation().z_degrees)
            self.setValue("Tag ID", tag_id)

            # Convert tx, ty into a Pose2d object and set robot pose
            # robot_pose = ApriltagPipeline.calculatePoseOnFeild(
            #     estimation, tag_id, self.apmap, estimation.z, estimation.x
            # )
            # speker_pose = ApriltagPipeline.calculatePoseOnFeild(
            #     estimation, 7, self.apmap, 0, 0
            # )

        return img_gray
