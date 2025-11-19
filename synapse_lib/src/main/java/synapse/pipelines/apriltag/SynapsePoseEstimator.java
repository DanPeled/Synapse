package synapse.pipelines.apriltag;

import java.util.Optional;

import edu.wpi.first.math.geometry.Pose3d;
import edu.wpi.first.math.geometry.Transform3d;

public class SynapsePoseEstimator {
    private EstimationRejectionConstraints m_estimationRejectionConstraints = new EstimationRejectionConstraints();
    private Transform3d m_cameraToRobotTransform;

    public SynapsePoseEstimator withCameraToRobotTransform(Transform3d cameraToRobotTransform) {
        m_cameraToRobotTransform = cameraToRobotTransform;
        return this;
    }

    public SynapsePoseEstimator withRobotToCameraTransform(Transform3d robotToCameraTransform) {
        m_cameraToRobotTransform = robotToCameraTransform.inverse();
        return this;
    }

    public SynapsePoseEstimator withEstimationRejectionConstraints(
            EstimationRejectionConstraints rejectionConstraints) {
        m_estimationRejectionConstraints = rejectionConstraints;
        return this;
    }

    public SynapsePoseEstimator withEstimationRejectionConstraints(
            java.util.function.UnaryOperator<EstimationRejectionConstraints> config) {
        m_estimationRejectionConstraints = config.apply(m_estimationRejectionConstraints);
        return this;
    }

    public RobotPoseEstimate estimate(Pose3d cameraPoseFieldSpace, long timestamp) {
        return new RobotPoseEstimate(cameraPoseFieldSpace.plus(m_cameraToRobotTransform), timestamp);
    }

    public Optional<RobotPoseEstimate> estimate(ApriltagResult apriltagResult) {
        return Optional.of(estimate(apriltagResult.getCameraEstimateFieldSpace3D(), apriltagResult.timestamp));
    }

    public static class EstimationRejectionConstraints {
        public float maxError = Float.MAX_VALUE;
        public float maxTagDistance = Float.MAX_VALUE;

        public EstimationRejectionConstraints withMaxError(float maxError) {
            this.maxError = maxError;
            return this;
        }

        public EstimationRejectionConstraints withMaxTagDistance(float maxTagDistance) {
            this.maxTagDistance = maxTagDistance;
            return this;
        }
    }

    public static record RobotPoseEstimate(Pose3d robotPoseFieldSpace, long timestamp) {
    }
}
