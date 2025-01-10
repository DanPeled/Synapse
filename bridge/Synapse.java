package frc.vision;

import edu.wpi.first.math.geometry.Pose2d;
import edu.wpi.first.math.geometry.Pose3d;
import edu.wpi.first.math.geometry.Rotation2d;
import edu.wpi.first.math.geometry.Rotation3d;
import edu.wpi.first.math.geometry.Translation2d;
import edu.wpi.first.math.geometry.Translation3d;
import edu.wpi.first.networktables.NetworkTable;
import edu.wpi.first.networktables.NetworkTableEntry;
import edu.wpi.first.networktables.NetworkTableInstance;

public class Synapse {
  private NetworkTable m_table = NetworkTableInstance.getDefault().getTable("Synapse");

  public Synapse() {
  }

  public void setPipeline(int cameraIndex, long pipelineIndex) {
    getPipelineEntry(cameraIndex).setInteger(pipelineIndex);
  }

  public long getPipeline(int cameraIndex) {
    return getPipelineEntry(cameraIndex).getInteger(-1);
  }

  public StampedBotPose getRobotPose(int cameraIndex) {
    double[] poseArr = getDataEntryTable(cameraIndex, "field").getEntry("Robot").getDoubleArray(new double[3]);
    return new StampedBotPose(pose2DFromArr(poseArr), getDataEntry(cameraIndex, "timestamp").getDouble(-1));
  }

  public Pose3d getDeltaTagPose(int cameraIndex) {
    double[] poseArr = getDataEntry(cameraIndex, "deltaTagPose").getDoubleArray(new double[6]);
    return pose3DFromArr(poseArr);
  }

  public NetworkTableEntry getDataEntry(int cameraIndex, String dataKey) {
    return getDataResultsTable(cameraIndex).getEntry(dataKey);
  }

  public NetworkTable getDataEntryTable(int cameraIndex, String dataKey) {
    return getDataResultsTable(cameraIndex).getSubTable(dataKey);
  }

  public NetworkTable getDataResultsTable(int cameraIndex) {
    return getCameraTable(cameraIndex).getSubTable("data");
  }

  private NetworkTableEntry getPipelineEntry(int cameraIndex) {
    return getCameraTable(cameraIndex).getEntry("pipeline");
  }

  private NetworkTable getCameraTable(int cameraIndex) {
    return m_table.getSubTable(String.format("camera%d", cameraIndex));
  }

  public static Pose3d pose3DFromArr(double[] arr) {
    return new Pose3d(
        new Translation3d(arr[0], arr[1], arr[2]), new Rotation3d(arr[3], arr[4], arr[5]));
  }

  public static Pose2d pose2DFromArr(double[] arr) {
    return new Pose2d(
        new Translation2d(arr[0], arr[1]), Rotation2d.fromDegrees(arr[2]));
  }
}
