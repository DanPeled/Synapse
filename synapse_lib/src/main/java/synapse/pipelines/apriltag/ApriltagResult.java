package synapse.pipelines.apriltag;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.Arrays;
import java.util.Objects;

/**
 * Represents the result of detecting an AprilTag. Contains information about the tag ID, detection
 * accuracy, and the estimated pose of the robot in different coordinate spaces.
 */
public class ApriltagResult {

  /** The unique ID of the detected AprilTag. Serialized/deserialized as "tag_id" in JSON. */
  @JsonProperty("tag_id")
  public int tagID;

  /**
   * The Hamming distance of the detected tag, representing the number of bit errors. Lower values
   * indicate a more accurate detection.
   */
  public float hamming;

  /** The estimated pose of the robot in the field coordinate system. */
  public double[] robotPose_fieldSpace;

  /** The estimated pose of the robot relative to the detected tag. */
  public double[] robotPose_tagSpace;

  /** The estimated pose of the tag in screen coordinates. */
  public double[] tagPose_screenSpace;

  /** The estimated pose(s) of the detected AprilTag. */
  public ApriltagPoseEstimate tag_estimate;

  /** Default constructor for Jackson and general instantiation. */
  public ApriltagResult() {}

  /**
   * Compares this {@code ApriltagResult} with another object for equality.
   *
   * <p>Two {@code ApriltagResult} objects are considered equal if all of the following are true:
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
    if (!(o instanceof ApriltagResult)) return false;
    ApriltagResult that = (ApriltagResult) o;
    return tagID == that.tagID
        && Float.compare(that.hamming, hamming) == 0
        && Arrays.equals(robotPose_fieldSpace, that.robotPose_fieldSpace)
        && Arrays.equals(robotPose_tagSpace, that.robotPose_tagSpace)
        && Arrays.equals(tagPose_screenSpace, that.tagPose_screenSpace)
        && Objects.equals(tag_estimate, that.tag_estimate);
  }

  /**
   * Computes a hash code for this {@code ApriltagResult}.
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
