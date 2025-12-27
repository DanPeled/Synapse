package synapse.pipelines.apriltag;

import edu.wpi.first.math.geometry.Pose3d;
import edu.wpi.first.math.geometry.Rotation3d;

public final class ApriltagPoseUtil {

  private ApriltagPoseUtil() {
    // Utility class — do not instantiate
  }

  /**
   * Converts a pose array to a {@link Pose3d}.
   *
   * <p>Expected format: {@code [x, y, z, roll, pitch, yaw]}, where angles are in <b>degrees</b>.
   *
   * @param pose the pose array
   * @return a {@link Pose3d}, or {@code null} if the input is invalid
   */
  public static Pose3d toPose3d(double[] pose) {
    if (pose == null || pose.length != 6) {
      return null;
    }

    double x = pose[0];
    double y = pose[1];
    double z = pose[2];

    double rollRad = Math.toRadians(pose[3]);
    double pitchRad = Math.toRadians(pose[4]);
    double yawRad = Math.toRadians(pose[5]);

    return new Pose3d(x, y, z, new Rotation3d(rollRad, pitchRad, yawRad));
  }
}
