package synapse;

import com.fasterxml.jackson.annotation.JsonProperty;
import edu.wpi.first.math.geometry.Pose2d;
import edu.wpi.first.math.geometry.Pose3d;

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

  /**
   * The estimated pose of the robot in the field coordinate system. This represents the robot's
   * position and orientation relative to the field.
   */
  public Pose3d robotPose_fieldSpace;

  /**
   * The estimated pose of the robot relative to the detected tag. Useful for tag-relative
   * localization and navigation.
   */
  public Pose3d robotPose_tagSpace;

  /**
   * The estimated pose of the robot in screen coordinates, typically used for visualizations or UI
   * overlays.
   */
  public Pose2d robotPose_screenSpace;

  /**
   * Default constructor for Jackson deserialization and general instantiation.
   *
   * <p>Initializes an empty ApriltagResult. All fields are set to their default values: numeric
   * types to 0, and object references to {@code null}.
   */
  public ApriltagResult() {}
}
