package synapse.pipelines.apriltag;

import java.util.Arrays;
import java.util.Objects;

/**
 * Represents the estimated pose(s) of an AprilTag detection.
 *
 * <p>AprilTag pose estimation can sometimes produce two possible poses due to ambiguity. This class
 * stores both candidate poses along with their associated error values, allowing downstream code to
 * choose the most reliable estimate.
 */
public class ApriltagPoseEstimate {

  /**
   * The error metric (e.g., reprojection or fitting error) associated with {@link #pose1}. Lower
   * values indicate higher confidence in the estimated pose.
   */
  public double error1;

  /**
   * The error metric (e.g., reprojection or fitting error) associated with {@link #pose2}. Lower
   * values indicate higher confidence in the estimated pose.
   */
  public double error2;

  /** The first possible 3D transform of the AprilTag relative to the camera or robot frame. */
  public double[] pose1;

  /**
   * The second possible 3D transform of the AprilTag relative to the camera or robot frame. This is
   * typically the ambiguous alternative to {@link #pose1}.
   */
  public double[] pose2;

  /**
   * Creates a new {@code ApriltagPoseEstimate} with all errors set to {@code 0.0} and poses
   * initialized to {@code null}.
   *
   * <p>This constructor is primarily provided for frameworks or serializers that require a
   * no-argument constructor. In most cases, values should be populated explicitly after
   * construction.
   */
  public ApriltagPoseEstimate() {}

  /**
   * Compares this {@code ApriltagPoseEstimate} with another object for equality.
   *
   * <p>Two {@code ApriltagPoseEstimate} objects are considered equal if all of the following are
   * true:
   *
   * <ul>
   *   <li>Their {@link #error1} and {@link #error2} values are numerically equal.
   *   <li>Their {@link #pose1} and {@link #pose2} arrays contain the same elements in the same
   *       order.
   * </ul>
   *
   * @param o the object to compare with this instance
   * @return {@code true} if the objects are equal, {@code false} otherwise
   */
  @Override
  public boolean equals(Object o) {
    if (this == o) return true;
    if (!(o instanceof ApriltagPoseEstimate)) return false;
    ApriltagPoseEstimate that = (ApriltagPoseEstimate) o;
    return Double.compare(that.error1, error1) == 0
        && Double.compare(that.error2, error2) == 0
        && Arrays.equals(pose1, that.pose1)
        && Arrays.equals(pose2, that.pose2);
  }

  /**
   * Computes a hash code for this {@code ApriltagPoseEstimate}.
   *
   * <p>The hash code is based on the same fields used in {@link #equals(Object)}: {@link #error1},
   * {@link #error2}, {@link #pose1}, and {@link #pose2}.
   *
   * @return a hash code value for this object
   */
  @Override
  public int hashCode() {
    int result = Objects.hash(error1, error2);
    result = 31 * result + Arrays.hashCode(pose1);
    result = 31 * result + Arrays.hashCode(pose2);
    return result;
  }
}
