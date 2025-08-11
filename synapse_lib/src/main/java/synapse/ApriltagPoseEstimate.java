package synapse;

import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * Represents an estimate of the pose (position and orientation) of an AprilTag. Includes two
 * possible pose solutions with their associated errors and ambiguity score.
 */
public class ApriltagPoseEstimate {

  /** The first possible pose estimate as a 6-element array [x, y, z, roll, pitch, yaw]. */
  @JsonProperty("pose1")
  private double[] m_pose1;

  /** The second possible pose estimate as a 6-element array [x, y, z, roll, pitch, yaw]. */
  @JsonProperty("pose2")
  private double[] m_pose2;

  /** The error associated with the first pose estimate. */
  @JsonProperty("error1")
  private float m_error1;

  /** The error associated with the second pose estimate. */
  @JsonProperty("error2")
  private float m_error2;

  /** The ambiguity score representing confidence in the pose estimates. */
  @JsonProperty("ambiguity")
  private float m_ambiguity;

  /**
   * Returns the first possible pose estimate.
   *
   * @return a double array containing [x, y, z, roll, pitch, yaw] for pose1
   */
  public double[] getPose1() {
    return m_pose1;
  }

  /**
   * Returns the second possible pose estimate.
   *
   * @return a double array containing [x, y, z, roll, pitch, yaw] for pose2
   */
  public double[] getPose2() {
    return m_pose2;
  }

  /**
   * Returns the error value associated with the first pose estimate.
   *
   * @return the error for pose1
   */
  public float getError1() {
    return m_error1;
  }

  /**
   * Returns the error value associated with the second pose estimate.
   *
   * @return the error for pose2
   */
  public float getError2() {
    return m_error2;
  }

  /**
   * Returns the ambiguity score indicating confidence in the pose estimates.
   *
   * @return the ambiguity score
   */
  public float getAmbiguity() {
    return m_ambiguity;
  }

  /**
   * Constructs an ApriltagPoseEstimate instance.
   *
   * @param m_pose1 The first possible pose estimate [x, y, z, roll, pitch, yaw].
   * @param m_pose2 The second possible pose estimate [x, y, z, roll, pitch, yaw].
   * @param m_error1 The error associated with the first pose estimate.
   * @param m_error2 The error associated with the second pose estimate.
   * @param m_ambiguity The ambiguity score representing confidence in the pose estimates.
   */
  public ApriltagPoseEstimate(
      double[] m_pose1, double[] m_pose2, float m_error1, float m_error2, float m_ambiguity) {
    this.m_pose1 = m_pose1;
    this.m_pose2 = m_pose2;
    this.m_error1 = m_error1;
    this.m_error2 = m_error2;
    this.m_ambiguity = m_ambiguity;
  }
}
