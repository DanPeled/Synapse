package synapse;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonMappingException;
import com.fasterxml.jackson.databind.ObjectMapper;

import edu.wpi.first.networktables.NetworkTable;
import edu.wpi.first.networktables.NetworkTableEntry;
import edu.wpi.first.networktables.NetworkTableInstance;

public class SynapseCamera {
  public static final String kSynapseTable = "Synapse";
  private final int m_id;
  private NetworkTable m_table, m_dataTable, m_settingsTable;

  public SynapseCamera(int id) {
    m_id = id;

    m_table = NetworkTableInstance.getDefault()
        .getTable(kSynapseTable)
        .getSubTable("camera" + m_id);
  }

  public List<ApriltagResult> getApriltagResults() throws IllegalArgumentException {
    String jsonString = getDataEntry("results").getString("[{}]");
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
          throw new IllegalArgumentException("[Synapse] : Error - Non-apriltag result: " + type);
        }
      } catch (JsonMappingException e) {
        e.printStackTrace();
      } catch (JsonProcessingException e) {
        e.printStackTrace();
      }
    }
    return new ArrayList<>();
  }

  public int getCameraID() {
    return m_id;
  }

  private NetworkTableEntry getDataEntry(String dataKey) {
    return getDataResultsTable().getEntry(dataKey);
  }

  private NetworkTable getDataResultsTable() {
    if (m_dataTable == null) {
      m_dataTable = m_table.getSubTable("data");
    }
    return m_dataTable;
  }

  private NetworkTable getSettingsTable() {
    if (m_settingsTable == null) {
      m_settingsTable = m_table.getSubTable("settings");
    }
    return m_settingsTable;
  }

  public static class CameraSettings {
    public static final String kBrightness = "brightness";
  }
}
