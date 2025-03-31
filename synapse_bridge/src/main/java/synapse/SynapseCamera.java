package synapse;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonMappingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import edu.wpi.first.networktables.NetworkTable;
import edu.wpi.first.networktables.NetworkTableEntry;
import edu.wpi.first.networktables.NetworkTableInstance;
import edu.wpi.first.networktables.NetworkTableType;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

public class SynapseCamera {
  public static final String kSynapseTable = "Synapse";
  public static final String kPipelineTopic = "pipeline";
  private static Map<Class<?>, String> registeredResultTypes = new HashMap<>();

  private final int m_id;
  private NetworkTable m_table, m_dataTable, m_settingsTable;
  private NetworkTableEntry m_pipelineEntry;

  public SynapseCamera(int id) {
    m_id = id;

    m_table =
        NetworkTableInstance.getDefault().getTable(kSynapseTable).getSubTable("camera" + m_id);
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

  public <T> List<T> getResults(Class<T> clazz) throws IllegalArgumentException {
    return getResults("results", clazz);
  }

  public <T> List<T> getResults(String resultsKey, Class<T> clazz) throws IllegalArgumentException {
    String jsonString = getDataEntry(resultsKey).getString("[{}]");
    if (jsonString.equals("[{}]") || jsonString.isEmpty()) {
      return new ArrayList<>();
    } else {
      ObjectMapper objectMapper = new ObjectMapper();
      List<T> resultList;
      try {
        Map<String, Object> resultMap =
            objectMapper.readValue(jsonString, new TypeReference<Map<String, Object>>() {});
        String requestedTypeString = "";

        if (!registeredResultTypes.containsKey(clazz)) {
          if (clazz.isAnnotationPresent(RegisterSynapseResult.class)) {
            requestedTypeString = clazz.getAnnotation(RegisterSynapseResult.class).type();
            registeredResultTypes.put(clazz, requestedTypeString);
          } else {
            throw new RuntimeException(
                String.format(
                    "[Synapse] Error: Class %s is missing the required @RegisterSynapseResult annotation.",
                    clazz.getName()));
          }
        } else {
          requestedTypeString = registeredResultTypes.get(clazz);
        }

        String actualTypeString = (String) resultMap.get("type");
        if (actualTypeString.equals(requestedTypeString)) {
          resultList =
              objectMapper.convertValue(resultMap.get("data"), new TypeReference<List<T>>() {});
          return resultList;

        } else {
          throw new RuntimeException(
              String.format(
                  "[Synapse] Error: Type mismatch detected. Expected: %s, but found: %s (from JSON).",
                  requestedTypeString, actualTypeString));
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

  public void setSetting(String key, double value) throws RuntimeException {
    NetworkTableEntry entry = getSettingsTable().getEntry(key);
    if (entry.getType() == NetworkTableType.kDouble) {
      entry.setDouble(value);
    } else {
      throwTypeMismatchException(key, entry.getType(), "double");
    }
  }

  public void setSetting(String key, double[] value) throws RuntimeException {
    NetworkTableEntry entry = getSettingsTable().getEntry(key);
    if (entry.getType() == NetworkTableType.kDoubleArray) {
      entry.setDoubleArray(value);
    } else {
      throwTypeMismatchException(key, entry.getType(), "double[]");
    }
  }

  public void setSetting(String key, String value) throws RuntimeException {
    NetworkTableEntry entry = getSettingsTable().getEntry(key);
    if (entry.getType() == NetworkTableType.kString) {
      entry.setString(value);
    } else {
      throwTypeMismatchException(key, entry.getType(), "String");
    }
  }

  public void setSetting(String key, String[] value) throws RuntimeException {
    NetworkTableEntry entry = getSettingsTable().getEntry(key);
    if (entry.getType() == NetworkTableType.kStringArray) {
      entry.setStringArray(value);
    } else {
      throwTypeMismatchException(key, entry.getType(), "StringArray");
    }
  }

  public void setSetting(String key, long value) throws RuntimeException {
    NetworkTableEntry entry = getSettingsTable().getEntry(key);
    if (entry.getType() == NetworkTableType.kInteger) {
      entry.setInteger(value);
    } else {
      throwTypeMismatchException(key, entry.getType(), "Integer");
    }
  }

  public void setSetting(String key, long[] value) throws RuntimeException {
    NetworkTableEntry entry = getSettingsTable().getEntry(key);
    if (entry.getType() == NetworkTableType.kIntegerArray) {
      entry.setIntegerArray(value);
    } else {
      throwTypeMismatchException(key, entry.getType(), "Integer[]");
    }
  }

  private void throwTypeMismatchException(String key, NetworkTableType actual, String expected) {
    throw new RuntimeException(
        String.format(
            "[Synapse]: Type mismatch for setting (%s). Expected: %s, but found: %s",
            key, expected, actual.toString()));
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
