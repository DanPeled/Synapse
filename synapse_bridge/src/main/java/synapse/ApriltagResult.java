package synapse;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.annotation.JsonDeserialize;
import edu.wpi.first.math.geometry.Pose3d;

@RegisterSynapseResult(type = "apriltag")
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
  private Pose3d robotPose_fieldSpace;

  @JsonDeserialize(using = Pose3dDeserializer.class)
  private Pose3d cameraPose_tagSpace;

  @JsonDeserialize(using = Pose3dDeserializer.class)
  private Pose3d robotPose_tagSpace;

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

  public Pose3d getRobotPose_fieldSpace() {
    return robotPose_fieldSpace;
  }

  public Pose3d getRobotPose_tagSpace() {
    return robotPose_tagSpace;
  }

  public Pose3d getCameraPose_tagSpace() {
    return cameraPose_tagSpace;
  }
}
