package frc.robot.subsystems.vision;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonMappingException;
import com.fasterxml.jackson.databind.ObjectMapper;

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
  private static NetworkTable m_table = NetworkTableInstance.getDefault().getTable("Synapse");

  public static void setPipeline(int cameraIndex, long pipelineIndex) {
    getPipelineEntry(cameraIndex).setInteger(pipelineIndex);
  }

  public static long getPipeline(int cameraIndex) {
    return getPipelineEntry(cameraIndex).getInteger(-1);
  }

  public static Pose3d getDeltaTagPose(int cameraIndex) {
    double[] poseArr = getDataEntry(cameraIndex, "deltaTagPose").getDoubleArray(new double[6]);
    return pose3DFromArr(poseArr);
  }

  public static NetworkTableEntry getDataEntry(int cameraIndex, String dataKey) {
    return getDataResultsTable(cameraIndex).getEntry(dataKey);
  }

  public static NetworkTable getDataEntryTable(int cameraIndex, String dataKey) {
    return getDataResultsTable(cameraIndex).getSubTable(dataKey);
  }

  public static NetworkTable getDataResultsTable(int cameraIndex) {
    return getCameraTable(cameraIndex).getSubTable("data");
  }

  private static NetworkTableEntry getPipelineEntry(int cameraIndex) {
    return getCameraTable(cameraIndex).getEntry("pipeline");
  }

  private static NetworkTable getCameraTable(int cameraIndex) {
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

  public static List<ApriltagResult> getResults(int cameraIndex) throws IllegalArgumentException {
    String jsonString = getDataEntry(cameraIndex, "results").getString("[{}]");
    if (jsonString.equals("[{}]")) {
      return new ArrayList<>();
    } else {
      ObjectMapper objectMapper = new ObjectMapper();
      List<ApriltagResult> resultList;
      try {
        Map<String, Object> resultMap = objectMapper.readValue(jsonString, new TypeReference<Map<String, Object>>() {
        });

        String type = (String) resultMap.get("type");
        if (type.equals("apriltag")) {
          resultList = objectMapper.convertValue(resultMap.get("data"), new TypeReference<List<ApriltagResult>>() {
          });
          return resultList;
        } else {
          throw new IllegalArgumentException("[Synapse] : Error - Non-existent result type: " + type);
        }
      } catch (JsonMappingException e) {
        e.printStackTrace();
      } catch (JsonProcessingException e) {
        e.printStackTrace();
      }
    }
    return new ArrayList<>();
  }
}
