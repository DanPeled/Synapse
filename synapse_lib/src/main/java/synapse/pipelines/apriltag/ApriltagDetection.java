package synapse.pipelines.apriltag;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.Arrays;
import java.util.Objects;

/**
 * Represents a single detected AprilTag along with its associated metadata and pose estimate.
 *
 * <p>This class contains the tag's ID, detection accuracy metrics, and the tag's estimated pose in
 * screen space. It is typically produced by an AprilTag detection pipeline.
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

  /** The estimated pose of the detected AprilTag in screen space. */
  public float[] tagPose_screenSpace;

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
   * @param o the object to compare with this instance
   * @return {@code true} if the objects are equal, {@code false} otherwise
   */
  @Override
  public boolean equals(Object o) {
    if (this == o) return true;
    if (!(o instanceof ApriltagDetection)) return false;
    ApriltagDetection that = (ApriltagDetection) o;
    return tagID == that.tagID
        && Float.compare(that.hamming, hamming) == 0
        && Arrays.equals(tagPose_screenSpace, that.tagPose_screenSpace);
  }

  /**
   * Computes a hash code for this {@code ApriltagDetection}.
   *
   * @return a hash code value for this object
   */
  @Override
  public int hashCode() {
    return Objects.hash(tagID, hamming, Arrays.hashCode(tagPose_screenSpace));
  }
}
