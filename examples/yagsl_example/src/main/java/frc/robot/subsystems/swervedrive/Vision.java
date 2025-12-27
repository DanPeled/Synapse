package frc.robot.subsystems.swervedrive;

import java.util.Optional;

import edu.wpi.first.math.Matrix;
import edu.wpi.first.math.VecBuilder;
import edu.wpi.first.math.geometry.Pose3d;
import edu.wpi.first.math.geometry.Rotation3d;
import edu.wpi.first.math.geometry.Transform3d;
import edu.wpi.first.math.geometry.Translation3d;
import edu.wpi.first.math.numbers.N1;
import edu.wpi.first.math.numbers.N3;
import edu.wpi.first.math.util.Units;
import swervelib.SwerveDrive;
import swervelib.telemetry.SwerveDriveTelemetry;
import synapse.SynapseCamera;
import synapse.SynapsePipelineType;
import synapse.pipelines.apriltag.ApriltagResult;

public class Vision {
    public static enum Camera {
        kMonochrome("Monochrome", "Synapse",
                new Rotation3d(0, Math.toRadians(-24.094), Math.toRadians(30)),
                new Translation3d(Units.inchesToMeters(12.056),
                        Units.inchesToMeters(10.981),
                        Units.inchesToMeters(8.44)),
                VecBuilder.fill(4, 4, 8));

        private final String name;
        private final String coprocessorName;
        private final Transform3d robotToCameraTransform3d;
        private final Matrix<N3, N1> curStdDevs;
        private final SynapseCamera camera;

        Camera(String name, String coprocessorName, Rotation3d rotationOffset,
                Translation3d translationOffset, Matrix<N3, N1> stdDevs) {
            this.name = name;
            this.coprocessorName = coprocessorName;
            this.robotToCameraTransform3d = new Transform3d(translationOffset, rotationOffset);
            this.curStdDevs = stdDevs;

            this.camera = new SynapseCamera(name, coprocessorName)
                    .withRobotToCameraOffset(robotToCameraTransform3d);
        }
    }

    public void updatePoseEstimation(SwerveDrive swerveDrive) {
        for (Camera camera : Camera.values()) {
            
        }
    }

    public Optional<Pose3d> getEstimatedRobotPose(Camera camera) {
        if (camera.camera.getPipelineType() != SynapsePipelineType.kApriltag.typestring)
            return Optional.empty(); // Roobt pose estimation uses apriltag pipeline

        Optional<ApriltagResult> results = camera.camera.getResults(SynapsePipelineType.kApriltag);
        if (results.isPresent()) {
            return Optional.of(camera.camera.estimateRobotPose(results.get().cameraEstimateFieldSpace3D()));
        } else {
            return Optional.empty();
        }
    }
}
