from wpimath.geometry import Pose2d, Rotation2d  
import json
import os
from pipeline import Pipeline
import robotpy_apriltag as apriltags
from synapse.pipeline_settings import PipelineSettings
from synapse.synapse import Pipeline
import cv2
import wpimath.units as units
from wpilib import SmartDashboard
import internal_files
from wpilib import Field2d
import turtle
import math

class ApriltagPipeline(Pipeline):
    
    def __init__(self, settings: PipelineSettings):
        self.settings = settings
        self.target_tag = settings["target_tag"]
        self.detector = apriltags.AprilTagDetector()
        self.detector.addFamily("tag36h11")
        self.pose_estimator_config = apriltags.AprilTagPoseEstimator.Config(
            units.meters(0.1651), 1279, 719, 640, 0
        )
        self.pose_estimator = apriltags.AprilTagPoseEstimator(
            self.pose_estimator_config
        )

    def process_frame(self, img, timestamp: float):
        if len(img.shape) == 3:
            img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            img_gray = img

        detections = self.detector.detect(img_gray)
        img_gray = cv2.cvtColor(img_gray, cv2.COLOR_GRAY2RGB)

        for detection in detections:
            if detection.getId() != self.target_tag:
                print(detection.getId())
                continue

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

            self.tx = ((center.x / 640) * 111.95855) - 111.95855/2
            self.ty = ((-center.y / 480) * 45) + 22.5

            SmartDashboard.putNumber("tx", self.tx)
            SmartDashboard.putNumber("ty", self.ty)
            SmartDashboard.putNumber("cy", center.y)
            SmartDashboard.putNumber("TX", estimation.x)
            SmartDashboard.putNumber("TY", estimation.y)
            SmartDashboard.putNumber("TZ", estimation.z)
            SmartDashboard.putNumber("RX", estimation.rotation().x_degrees)
            SmartDashboard.putNumber("RY", (estimation.rotation().y_degrees))
            SmartDashboard.putNumber("RZ", estimation.rotation().z_degrees)
            SmartDashboard.putNumber("Tag ID", tag_id)

            # Convert tx, ty into a Pose2d object and set robot pose
            robot_pose = ApriltagPipeline.calculatePoseOnFeild(estimation ,tag_id, self.apmap, estimation.z , estimation.x)
            speker_pose = ApriltagPipeline.calculatePoseOnFeild(estimation ,7, self.apmap, 0 , 0)
            self.speakerp.goto(((speker_pose[0] - 8.308467 )* 25), -((speker_pose[1] - 4.098925) * 25))
            self.my_turtle.goto(((robot_pose[0] - 8.308467 )* 25), -((robot_pose[1] - 4.098925) * 25))
            self.my_turtle.setheading(robot_pose[2])  # Correct usage of .degrees()

        return img_gray
