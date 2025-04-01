package synapse;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.annotation.JsonDeserialize;
import edu.wpi.first.math.geometry.Pose3d;

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

  /** The family of the detected AprilTag. */
  @JsonProperty("tag_family")
  private String tagFamily;

  /** The unique ID of the detected AprilTag. */
  @JsonProperty("tag_id")
  private int tagID;

  /** Hamming distance used for error correction. */
  @JsonProperty("hamming")
  private double hamming;

  /** Decision margin indicating the confidence of the tag detection. */
  @JsonProperty("decision_margin")
  private double decisionMargin;

  /** Homography matrix describing the transformation. */
  @JsonProperty("homography")
  private double[][] homography;

  /** Center coordinates of the detected tag in image space. */
  @JsonProperty("center")
  private double[] center;

  /** Rotation matrix representing tag orientation. */
  @JsonProperty("pose_R")
  private double[][] pose_R;

  /** Translation vector representing tag position. */
  @JsonProperty("pose_t")
  private double[][] pose_t;

  /** Corner coordinates of the detected tag. */
  @JsonProperty("corners")
  private double[][] corners;

  /** Pose estimation error value. */
  @JsonProperty("pose_err")
  private double poseError;

  /** Estimated robot pose in field space. */
  @JsonDeserialize(using = Pose3dDeserializer.class)
  private Pose3d robotPose_fieldSpace;

  /** Estimated camera pose in tag space. */
  @JsonDeserialize(using = Pose3dDeserializer.class)
  private Pose3d cameraPose_tagSpace;

  /** Estimated robot pose in tag space. */
  @JsonDeserialize(using = Pose3dDeserializer.class)
  private Pose3d robotPose_tagSpace;

  /**
   * Gets the timestamp of the detection.
   *
   * @return the timestamp of the detection.
   */
  public double getTimestamp() {
    return timestamp;
  }

  /**
   * Gets the AprilTag family.
   *
   * @return the AprilTag family.
   */
  public String getTagFamily() {
    return tagFamily;
  }

  /**
   * Gets the ID of the detected tag.
   *
   * @return the ID of the detected tag.
   */
  public int getTagID() {
    return tagID;
  }

  /**
   * Gets the Hamming error correction value.
   *
   * @return the Hamming error correction value.
   */
  public double getHamming() {
    return hamming;
  }

  /**
   * Gets the confidence margin of the detection.
   *
   * @return the confidence margin of the detection.
   */
  public double getDecisionMargin() {
    return decisionMargin;
  }

  /**
   * Gets the homography matrix.
   *
   * @return the homography matrix.
   */
  public double[][] getHomography() {
    return homography;
  }

  /**
   * Gets the center of the detected tag in image space.
   *
   * @return the center of the detected tag in image space.
   */
  public double[] getCenter() {
    return center;
  }

  /**
   * Gets the rotation matrix of the tag.
   *
   * @return the rotation matrix of the tag.
   */
  public double[][] getPose_R() {
    return pose_R;
  }

  /**
   * Gets the translation vector of the tag.
   *
   * @return the translation vector of the tag.
   */
  public double[][] getPose_t() {
    return pose_t;
  }

  /**
   * Gets the coordinates of the tag corners.
   *
   * @return the coordinates of the tag corners.
   */
  public double[][] getCorners() {
    return corners;
  }

  /**
   * Gets the pose estimation error.
   *
   * @return the pose estimation error.
   */
  public double getPoseError() {
    return poseError;
  }

  /**
   * Gets the estimated robot pose in field space.
   *
   * @return the estimated robot pose in field space.
   */
  public Pose3d getRobotPose_fieldSpace() {
    return robotPose_fieldSpace;
  }

  /**
   * Gets the estimated robot pose in tag space.
   *
   * @return the estimated robot pose in tag space.
   */
  public Pose3d getRobotPose_tagSpace() {
    return robotPose_tagSpace;
  }

  /**
   * Gets the estimated camera pose in tag space.
   *
   * @return the estimated camera pose in tag space.
   */
  public Pose3d getCameraPose_tagSpace() {
    return cameraPose_tagSpace;
  }
}
