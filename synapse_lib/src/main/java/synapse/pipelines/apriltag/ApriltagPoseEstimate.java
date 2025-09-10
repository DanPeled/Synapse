package synapse.pipelines.apriltag;

import java.util.Arrays;
import java.util.Objects;

/**
 * Represents the candidate 3D pose estimates of an AprilTag detection.
 *
 * <p>When estimating the pose of an AprilTag, the algorithm may return two possible solutions due
 * to perspective ambiguity. This class stores both candidate poses along with their associated
 * error metrics, allowing downstream logic to determine which pose is more reliable.
 *
 * <p>Each pose is represented as a 6-element array of doubles: {@code [x, y, z, roll, pitch, yaw]}.
 */
public class ApriltagPoseEstimate {

  /**
   * The error metric (e.g., reprojection error) associated with {@link #acceptedPose}. Lower values
   * indicate higher confidence in this candidate pose.
   */
  public double acceptedError;

  /**
   * The error metric (e.g., reprojection error) associated with {@link #rejectedPose}. Lower values
   * indicate higher confidence in this candidate pose.
   */
  public double rejectedError;

  /**
   * The first possible 3D pose of the AprilTag relative to the camera or robot frame, represented
   * as {@code [x, y, z, roll, pitch, yaw]}.
   *
   * <p>This pose is generally selected as the more reliable estimate, based on the associated error
   * value.
   */
  public double[] acceptedPose;

  /**
   * The second possible 3D pose of the AprilTag relative to the camera or robot frame, represented
   * as {@code [x, y, z, roll, pitch, yaw]}.
   *
   * <p>This pose is typically the ambiguous alternative to {@link #acceptedPose}.
   */
  public double[] rejectedPose;

  /**
   * Creates a new {@code ApriltagPoseEstimate} with errors initialized to {@code 0.0} and poses set
   * to {@code null}.
   *
   * <p>This no-argument constructor exists primarily for use by serialization frameworks. In most
   * cases, values should be assigned explicitly after construction.
   */
  public ApriltagPoseEstimate() {}

  /**
   * Checks whether this {@code ApriltagPoseEstimate} is equal to another object.
   *
   * <p>Two instances are considered equal if and only if:
   *
   * <ul>
   *   <li>Their {@link #acceptedError} and {@link #rejectedError} values are equal, and
   *   <li>Their {@link #acceptedPose} and {@link #rejectedPose} arrays contain the same elements in
   *       the same order.
   * </ul>
   *
   * @param o the object to compare with this instance
   * @return {@code true} if the objects are equal; {@code false} otherwise
   */
  @Override
  public boolean equals(Object o) {
    if (this == o) return true;
    if (!(o instanceof ApriltagPoseEstimate)) return false;
    ApriltagPoseEstimate that = (ApriltagPoseEstimate) o;
    return Double.compare(that.acceptedError, acceptedError) == 0
        && Double.compare(that.rejectedError, rejectedError) == 0
        && Arrays.equals(acceptedPose, that.acceptedPose)
        && Arrays.equals(rejectedPose, that.rejectedPose);
  }

  /**
   * Computes a hash code for this {@code ApriltagPoseEstimate}.
   *
   * <p>The hash code is derived from the same fields used in {@link #equals(Object)}: {@link
   * #acceptedError}, {@link #rejectedError}, {@link #acceptedPose}, and {@link #rejectedPose}.
   *
   * @return a hash code value for this object
   */
  @Override
  public int hashCode() {
    int result = Objects.hash(acceptedError, rejectedError);
    result = 31 * result + Arrays.hashCode(acceptedPose);
    result = 31 * result + Arrays.hashCode(rejectedPose);
    return result;
  }
}
