from pipeline import Pipeline
import robotpy_apriltag as apriltags
import cv2
import wpimath.units as units


class ApriltagPipeline(Pipeline):
    def __init__(self):
        self.detector = apriltags.AprilTagDetector()
        self.detector.addFamily("tag36h11")
        self.pose_estimator_config = apriltags.AprilTagPoseEstimator.Config(
            units.meters(0.1651), 1920, 1080, 0, 0
        )
        self.pose_estimator = apriltags.AprilTagPoseEstimator(
            self.pose_estimator_config
        )

    def process_frame(self, img, timestamp):
        if len(img.shape) == 3:
            img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            img_gray = img

        detections = self.detector.detect(img_gray)
        img_gray = cv2.cvtColor(img_gray, cv2.COLOR_GRAY2RGB)
        for detection in detections:
            center = detection.getCenter()
            cv2.putText(
                img_gray,
                f"{self.pose_estimator.estimate(detection)}",
                (10, 70),
                cv2.FONT_HERSHEY_SIMPLEX,
                1,
                (0, 255, 0),
                2,
            )
            cv2.circle(img_gray, (int(center.x), int(center.y)), 5, (0, 255, 0), -1)

        return img_gray
