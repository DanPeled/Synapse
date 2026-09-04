package synapse.pipelines.apriltag;

import com.fasterxml.jackson.annotation.JsonProperty;
import edu.wpi.first.math.geometry.Pose3d;
import edu.wpi.first.math.geometry.Rotation3d;
import edu.wpi.first.math.geometry.Translation3d;
import java.util.Arrays;

/**
 * Represents the result of detecting AprilTags in a single frame or input source.
 *
 * <p>This class contains the list of detected tags, an estimate of the camera's pose in field
 * space, and the reprojection error of the pose estimate. It is typically produced by an AprilTag
 * pipeline.
 */
public class ApriltagResult {

  /** The array of detected AprilTags with their associated detection data. */
  public ApriltagDetection[] tags;

  /**
   * The estimated camera pose in field space represented as an array of doubles.
   *
   * <p>The values are ordered as {@code [x, y, z, roll, pitch, yaw]}.
   */
  public double[] cameraEstimate_fieldSpace;

  /**
   * The reprojection error of the camera pose estimate.
   *
   * <p>This represents the error between the observed AprilTag image points and the points
   * projected into the image using the estimated camera pose. Lower values generally indicate a
   * better-fitting pose estimate.
   */
  @JsonProperty("reprojection_error")
  public float reprojectionError;

  /**
   * Creates a new, empty {@code ApriltagResult}.
   *
   * <p>This constructor is primarily used for JSON deserialization by Jackson and for general
   * instantiation when no initial values are provided.
   */
  public ApriltagResult() {}

  /**
   * Returns the camera's estimated pose in field space as a 3D pose.
   *
   * @return the camera's estimated field-space 3D pose
   */
  public Pose3d cameraEstimate_fieldSpace3d() {
    return new Pose3d(
        new Translation3d(
            cameraEstimate_fieldSpace[0],
            cameraEstimate_fieldSpace[1],
            cameraEstimate_fieldSpace[2]),
        new Rotation3d(
            cameraEstimate_fieldSpace[3],
            cameraEstimate_fieldSpace[4],
            cameraEstimate_fieldSpace[5]));
  }

  /**
   * Compares this result to another object for equality. Two results are considered equal if their
   * detected tags, camera field space estimates, and reprojection errors are equal.
   *
   * @param o the object to compare with
   * @return {@code true} if the objects are equal, otherwise {@code false}
   */
  @Override
  public boolean equals(Object o) {
    if (this == o) return true;
    if (!(o instanceof ApriltagResult)) return false;
    ApriltagResult that = (ApriltagResult) o;
    return Float.compare(reprojectionError, that.reprojectionError) == 0
        && Arrays.equals(tags, that.tags)
        && Arrays.equals(cameraEstimate_fieldSpace, that.cameraEstimate_fieldSpace);
  }

  /**
   * Computes a hash code for this result based on its detected tags, camera field space estimate,
   * and reprojection error.
   *
   * @return the computed hash code
   */
  @Override
  public int hashCode() {
    int result = Arrays.hashCode(tags);
    result = 31 * result + Arrays.hashCode(cameraEstimate_fieldSpace);
    result = 31 * result + Float.hashCode(reprojectionError);
    return result;
  }
}
