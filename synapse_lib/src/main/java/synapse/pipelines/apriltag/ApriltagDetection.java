package synapse.pipelines.apriltag;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.Arrays;
import java.util.Objects;

/**
 * Represents a single detected AprilTag along with its associated metadata and pose estimates.
 *
 * <p>This class contains the tag's ID, detection accuracy metrics. It is typically produced by an AprilTag detection
 * pipeline.
 */
public class ApriltagDetection {

  /**
   * The unique ID of the detected AprilTag.
   *
   * <p>Serialized/deserialized as {@code "tag_id"} in JSON.
   */
  @JsonProperty("tag_id")
  public int tagID;

  /**
   * The Hamming distance of the detected tag, representing the number of bit errors.
   *
   * <p>Lower values indicate a more accurate detection.
   */
  public float hamming;

  /**
   * Creates a new, empty {@code ApriltagDetection}.
   *
   * <p>This constructor is primarily used for JSON deserialization by Jackson and for general
   * instantiation when no initial values are provided.
   */
  public ApriltagDetection() {}

  /**
   * Compares this {@code ApriltagDetection} with another object for equality.
   *
   * <p>Two {@code ApriltagDetection} objects are considered equal if all of the following are true:
   *
   * <ul>
   *   <li>Their {@link #tagID} values are the same.
   *   <li>Their {@link #hamming} values are numerically equal.
   *   <li>Their {@link #cameraPose_fieldSpace}, {@link #cameraPose_tagSpace}, and {@link
   *       #tagPose_screenSpace} arrays contain the same elements in the same order.
   *   <li>Their {@link #tag_estimate} objects are equal according to {@link
   *       ApriltagPoseEstimate#equals(Object)}.
   * </ul>
   *
   * @param o the object to compare with this instance
   * @return {@code true} if the objects are equal, {@code false} otherwise
   */
  @Override
  public boolean equals(Object o) {
    if (this == o) return true;
    if (!(o instanceof ApriltagDetection)) return false;
    ApriltagDetection that = (ApriltagDetection) o;
    return tagID == that.tagID
        && Float.compare(that.hamming, hamming) == 0;
  }

  /**
   * Computes a hash code for this {@code ApriltagDetection}.
   *
   * <p>The hash code is based on the same fields used in {@link #equals(Object)}: {@link #tagID},
   * {@link #hamming}, {@link #cameraPose_fieldSpace}, {@link #cameraPose_tagSpace}, {@link
   * #tagPose_screenSpace}, and {@link #tag_estimate}.
   *
   * @return a hash code value for this object
   */
  @Override
  public int hashCode() {
    int result = Objects.hash(tagID, hamming);
    return result;
  }
}
