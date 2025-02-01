package frc.robot.subsystems.vision;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.annotation.JsonDeserialize;
import edu.wpi.first.math.geometry.Pose3d;

public class ApriltagResult {
  @JsonProperty("timestamp")
  private double timestamp;

  @JsonProperty("tag_family")
  private String tagFamily;

  @JsonProperty("tag_id")
  private int tagID;

  @JsonProperty("hamming")
  private double hamming;

  @JsonProperty("decision_margin")
  private double decisionMargin;

  @JsonProperty("homography")
  private double[][] homography;

  @JsonProperty("center")
  private double[] center;

  @JsonProperty("pose_R")
  private double[][] pose_R;

  @JsonProperty("pose_t")
  private double[][] pose_t;

  @JsonProperty("corners")
  private double[][] corners;

  @JsonProperty("pose_err")
  private double poseError;

  @JsonDeserialize(using = Pose3dDeserializer.class)
  private Pose3d robotPose;

  @JsonDeserialize(using = Pose3dDeserializer.class)
  private Pose3d tagRelativePose;

  @JsonDeserialize(using = Pose3dDeserializer.class)
  private Pose3d tagFieldPose;

  public double getTimestamp() {
    return timestamp;
  }

  public String getTagFamily() {
    return tagFamily;
  }

  public int getTagID() {
    return tagID;
  }

  public double getHamming() {
    return hamming;
  }

  public double getDecisionMargin() {
    return decisionMargin;
  }

  public double[][] getHomography() {
    return homography;
  }

  public double[] getCenter() {
    return center;
  }

  public double[][] getPose_R() {
    return pose_R;
  }

  public double[][] getPose_t() {
    return pose_t;
  }

  public double[][] getCorners() {
    return corners;
  }

  public double getPoseError() {
    return poseError;
  }

  public Pose3d getRobotPose() {
    return robotPose;
  }

  public Pose3d getTagRelativePose() {
    return tagRelativePose;
  }

  public Pose3d getTagFieldPose() {
    return tagFieldPose;
  }
}
