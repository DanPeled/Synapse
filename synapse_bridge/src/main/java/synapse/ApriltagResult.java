package synapse;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.Optional;

/** Represents the result of an AprilTag detection, including pose estimation and metadata. */
@RegisterSynapseResult(type = "apriltag")
public class ApriltagResult {
  /**
   * Default constructor for the {@link ApriltagResult} class.
   *
   * <p>This constructor should not be used directly.
   */
  public ApriltagResult() {}

  /** Timestamp of the detection. */
  @JsonProperty("timestamp")
  private double timestamp;

  /**
   * The unique ID of the detected AprilTag.
   *
   * <p>Present for verbosity levels: kTagDetectionData and above.
   */
  @JsonProperty("tag_id")
  private Optional<Integer> tagID;

  /**
   * Hamming distance used for error correction.
   *
   * <p>Present for verbosity levels: kTagDetails and above.
   */
  @JsonProperty("hamming")
  private Optional<Double> hamming;

  /**
   * Center coordinates of the detected tag in image space.
   *
   * <p>Present for verbosity levels: kTagDetectionData and above.
   */
  @JsonProperty("center")
  private Optional<double[]> center;

  /** Estimated robot pose in field space. */
  @JsonProperty("robotPose_fieldSpace")
  private double[] robotPose_fieldSpace;

  /** Estimated camera pose in tag space. */
  @JsonProperty("tag_estimate")
  private ApriltagPoseEstimate m_tagPoseEstimate;

  /** Estimated robot pose in tag space. */
  @JsonProperty("robotPose_tagSpace")
  private double[] robotPose_tagSpace;

  /**
   * Gets the timestamp of the detection.
   *
   * @return the timestamp of the detection.
   */
  public double getTimestamp() {
    return timestamp;
  }

  /**
   * Gets the ID of the detected tag.
   *
   * @return the ID of the detected tag.
   */
  public Optional<Integer> getTagID() {
    return tagID;
  }

  /**
   * Gets the Hamming error correction value.
   *
   * @return the Hamming error correction value.
   */
  public Optional<Double> getHamming() {
    return hamming;
  }

  /**
   * Gets the center of the detected tag in image space.
   *
   * @return the center of the detected tag in image space.
   */
  public Optional<double[]> getCenter() {
    return center;
  }

  /**
   * Gets the estimated robot pose in field space.
   *
   * @return the estimated robot pose in field space.
   */
  public double[] getRobotPose_fieldSpace() {
    return robotPose_fieldSpace;
  }

  /**
   * Gets the estimated robot pose in tag space.
   *
   * @return the estimated robot pose in tag space.
   */
  public double[] getRobotPose_tagSpace() {
    return robotPose_tagSpace;
  }

  /**
   * Gets the estimated camera pose in tag space.
   *
   * @return the estimated camera pose in tag space.
   */
  public ApriltagPoseEstimate getTagPoseEstimate() {
    return m_tagPoseEstimate;
  }

  public static enum ApriltagVerbosity {
    kPoseOnly(0),
    kTagDetails(1),
    kTagDetectionData(2),
    kAll(3);

    public final int level;

    ApriltagVerbosity(int level) {
      this.level = level;
    }
  }
}
