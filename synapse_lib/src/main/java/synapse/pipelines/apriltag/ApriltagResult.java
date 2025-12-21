package synapse.pipelines.apriltag;

import java.util.Arrays;

/**
 * Represents the result of detecting AprilTags in a single frame or input source.
 *
 * <p>This class contains the list of detected tags and an estimate of the camera's pose in field
 * space. It is typically produced by an AprilTag pipeline.
 */
public class ApriltagResult {

  /** The array of detected AprilTags with their associated detection data. */
  public ApriltagDetection[] tags;

  /**
   * The estimated camera pose in field space represented as an array of doubles.
   *
   * <p>({@code [x, y, z, roll, pitch, yaw]}).
   */
  public double[] cameraEstimate_fieldSpace;

  /**
   * Creates a new, empty {@code ApriltagResult}.
   *
   * <p>This constructor is primarily used for JSON deserialization by Jackson and for general
   * instantiation when no initial values are provided.
   */
  public ApriltagResult() {}

  /**
   * Compares this result to another object for equality. Two results are considered equal if both
   * their detected tags and camera field space estimates are equal.
   *
   * @param o the object to compare with
   * @return {@code true} if the objects are equal, otherwise {@code false}
   */
  @Override
  public boolean equals(Object o) {
    if (this == o) return true;
    if (!(o instanceof ApriltagResult)) return false;
    ApriltagResult that = (ApriltagResult) o;
    return Arrays.equals(tags, that.tags)
        && Arrays.equals(cameraEstimate_fieldSpace, that.cameraEstimate_fieldSpace);
  }

  /**
   * Computes a hash code for this result based on its detected tags and camera field space
   * estimate.
   *
   * @return the computed hash code
   */
  @Override
  public int hashCode() {
    int result = Arrays.hashCode(tags);
    result = 31 * result + Arrays.hashCode(cameraEstimate_fieldSpace);
    return result;
  }
}
