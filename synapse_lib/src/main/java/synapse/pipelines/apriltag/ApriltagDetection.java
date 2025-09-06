package synapse.pipelines.apriltag;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.Arrays;
import java.util.Objects;

/**
 * Represents a single detected AprilTag along with its associated metadata and pose estimates.
 *
 * <p>This class contains the tag's ID, detection accuracy metrics, and the estimated poses of the
 * robot and tag in multiple coordinate systems. It is typically produced by an AprilTag detection
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
   * The estimated pose of the robot in the <b>field coordinate system</b>.
   *
   * <p>Format: {@code [x, y, z, roll, pitch, yaw]}.
   */
  public double[] robotPose_fieldSpace;

  /**
   * The estimated pose of the robot relative to the <b>detected tag</b>.
   *
   * <p>Format: {@code [x, y, z, roll, pitch, yaw]}.
   */
  public double[] robotPose_tagSpace;

  /**
   * The estimated pose of the tag in <b>screen coordinates</b>.
   *
   * <p>Format: {@code [x, y, z, roll, pitch, yaw]}.
   */
  public double[] tagPose_screenSpace;

  /**
   * The estimated pose(s) of the detected AprilTag, including multiple hypotheses or refined
   * estimates if available.
   */
  public ApriltagPoseEstimate tag_estimate;

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
   *   <li>Their {@link #robotPose_fieldSpace}, {@link #robotPose_tagSpace}, and {@link
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
        && Float.compare(that.hamming, hamming) == 0
        && Arrays.equals(robotPose_fieldSpace, that.robotPose_fieldSpace)
        && Arrays.equals(robotPose_tagSpace, that.robotPose_tagSpace)
        && Arrays.equals(tagPose_screenSpace, that.tagPose_screenSpace)
        && Objects.equals(tag_estimate, that.tag_estimate);
  }

  /**
   * Computes a hash code for this {@code ApriltagDetection}.
   *
   * <p>The hash code is based on the same fields used in {@link #equals(Object)}: {@link #tagID},
   * {@link #hamming}, {@link #robotPose_fieldSpace}, {@link #robotPose_tagSpace}, {@link
   * #tagPose_screenSpace}, and {@link #tag_estimate}.
   *
   * @return a hash code value for this object
   */
  @Override
  public int hashCode() {
    int result = Objects.hash(tagID, hamming, tag_estimate);
    result = 31 * result + Arrays.hashCode(robotPose_fieldSpace);
    result = 31 * result + Arrays.hashCode(robotPose_tagSpace);
    result = 31 * result + Arrays.hashCode(tagPose_screenSpace);
    return result;
  }
}
