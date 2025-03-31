package synapse;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonMappingException;
import com.fasterxml.jackson.databind.ObjectMapper;

import edu.wpi.first.networktables.NetworkTable;
import edu.wpi.first.networktables.NetworkTableEntry;
import edu.wpi.first.networktables.NetworkTableInstance;

public class SynapseCamera {
  public static final String kSynapseTable = "Synapse";
  public static final String kPipelineTopic = "pipeline";

  private final int m_id;
  private NetworkTable m_table, m_dataTable, m_settingsTable;
  private NetworkTableEntry m_pipelineEntry;

  public SynapseCamera(int id) {
    m_id = id;

    m_table = NetworkTableInstance.getDefault()
        .getTable(kSynapseTable)
        .getSubTable("camera" + m_id);
  }

  public void setPipeline(long pipeline) {
    if (m_pipelineEntry == null) {
      m_pipelineEntry = m_table.getEntry(kPipelineTopic);
    }
    m_pipelineEntry.setInteger(pipeline);
  }

  public long getPipeline() {
    if (m_pipelineEntry == null) {
      m_pipelineEntry = m_table.getEntry(kPipelineTopic);
    }

    return m_pipelineEntry.getInteger(-1);
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

  public void setSetting(String key, Object value) {
    NetworkTableEntry entry = getSettingsTable().getEntry(key);
    if (value instanceof Double) {
      entry.setDouble((Double) value);
    } else if (value instanceof Double[]) {
      entry.setDoubleArray((Double[]) value);
    } else if (value instanceof String) {
      entry.setString((String) value);
    } else if (value instanceof String[]) {
      entry.setStringArray((String[]) value);
    } else if (value instanceof Integer || value instanceof Long) {
      entry.setInteger((Integer) value);
    } else if (value instanceof Long[]) {
      entry.setIntegerArray((Long[]) value);
    } else {
      throw new RuntimeException(
          String.format("[Synapse]: Unknown setting (%s) value type: %s", key, value.getClass().getSimpleName()));
    }
  }

  public Optional<Object> getSetting(String key) {
    NetworkTableEntry entry = getSettingsTable().getEntry(key);

    if (!entry.exists()) {
      return Optional.empty();
    }

    switch (entry.getType()) {
      case kDouble:
        return Optional.of(entry.getDouble(0.0));
      case kDoubleArray:
        return Optional.of(entry.getDoubleArray(new double[0]));
      case kString:
        return Optional.of(entry.getString(""));
      case kStringArray:
        return Optional.of(entry.getStringArray(new String[0]));
      case kInteger:
        return Optional.of(entry.getInteger(0));
      case kIntegerArray:
        return Optional.of(entry.getIntegerArray(new long[0]));
      default:
        return Optional.empty();
    }
  }

  public static class CameraSettings {
    public static final String kBrightness = "brightness";
    public static final String kGain = "gain";
    public static final String kExposure = "exposure";
    public static final String kOrientation = "orientation";
  }
}
