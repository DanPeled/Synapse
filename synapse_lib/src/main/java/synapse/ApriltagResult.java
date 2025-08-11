package synapse;

import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.Optional;

/** Represents the result of an AprilTag detection, including pose estimation and metadata. */
@RegisterSynapseResult(type = "apriltag")
public class ApriltagResult {
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

  /**
   * Constructs an ApriltagResult instance.
   *
   * @param timestamp Timestamp of the detection.
   * @param tagID Optional tag ID.
   * @param hamming Optional hamming distance.
   * @param center Optional center coordinates.
   * @param robotPose_fieldSpace Estimated robot pose in field space.
   * @param m_tagPoseEstimate Estimated camera pose in tag space.
   * @param robotPose_tagSpace Estimated robot pose in tag space.
   */
  public ApriltagResult(
      double timestamp,
      Optional<Integer> tagID,
      Optional<Double> hamming,
      Optional<double[]> center,
      double[] robotPose_fieldSpace,
      ApriltagPoseEstimate m_tagPoseEstimate,
      double[] robotPose_tagSpace) {
    this.timestamp = timestamp;
    this.tagID = tagID;
    this.hamming = hamming;
    this.center = center;
    this.robotPose_fieldSpace = robotPose_fieldSpace;
    this.m_tagPoseEstimate = m_tagPoseEstimate;
    this.robotPose_tagSpace = robotPose_tagSpace;
  }

  /**
   * Specifies the verbosity level for AprilTag processing output. Controls the amount of
   * information logged or displayed during detection.
   */
  public static enum ApriltagVerbosity {

    /** Only pose information will be output. This is the minimal verbosity setting. */
    kPoseOnly(0),

    /** Includes detailed information about the detected tags. */
    kTagDetails(1),

    /** Includes detailed tag detection data, such as corner detections. */
    kTagDetectionData(2),

    /**
     * Outputs all available debug and detection information. This is the maximum verbosity level.
     */
    kAll(3);

    /** The integer level representing verbosity */
    public final int level;

    /**
     * Constructs a verbosity level with the given integer representation.
     *
     * @param level the verbosity level as an integer
     */
    ApriltagVerbosity(int level) {
      this.level = level;
    }
  }
}
