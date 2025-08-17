package synapse;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jdk8.Jdk8Module;
import com.fasterxml.jackson.module.paramnames.ParameterNamesModule;
import edu.wpi.first.networktables.NetworkTable;
import edu.wpi.first.networktables.NetworkTableEntry;
import edu.wpi.first.networktables.NetworkTableInstance;
import edu.wpi.first.networktables.NetworkTableType;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.stream.Collectors;

/**
 * Represents a camera in the Synapse system, providing methods to manage settings and retrieve
 * results from NetworkTables.
 */
public class SynapseCamera {
  /** The name of the Synapse table in the NetworkTables */
  public static final String kSynapseTable = "Synapse";

  /** The topic for pipeline-related data */
  public static final String kPipelineTopic = "pipeline";

  /** The topic for recording status */
  public static final String kRecordStatusTopic = "record";

  /** A map for associating result classes with their corresponding data types as strings */
  private static Map<Class<?>, String> registeredResultTypes = new HashMap<>();

  /** Unique identifier for this Synapse instance */
  private final int m_id;

  /** The main NetworkTable instance used for storing and retrieving Synapse-related data */
  private NetworkTable m_table;

  /** The NetworkTable used for storing detection and result data */
  private NetworkTable m_dataTable;

  /** The NetworkTable used for storing camera and pipeline settings */
  private NetworkTable m_settingsTable;

  /** The NetworkTableEntry representing the selected vision processing pipeline */
  private NetworkTableEntry m_pipelineEntry;

  /** The NetworkTableEntry representing the camera's recording status */
  private NetworkTableEntry m_recordStateEntry;

  /**
   * Constructs a new SynapseCamera instance.
   *
   * @param id The camera ID.
   */
  public SynapseCamera(int id) {
    m_id = id;
    m_table =
        NetworkTableInstance.getDefault().getTable(kSynapseTable).getSubTable("camera" + m_id);
  }

  /**
   * Sets the camera pipeline.
   *
   * @param pipeline The pipeline ID to set.
   */
  public void setPipeline(long pipeline) {
    if (m_pipelineEntry == null) {
      m_pipelineEntry = m_table.getEntry(kPipelineTopic);
    }
    assert m_pipelineEntry != null;
    m_pipelineEntry.setInteger(pipeline);
  }

  /**
   * Gets the current pipeline ID.
   *
   * @return The current pipeline ID, or -1 if not set.
   */
  public long getPipeline() {
    if (m_pipelineEntry == null) {
      m_pipelineEntry = m_table.getEntry(kPipelineTopic);
    }
    assert m_pipelineEntry != null;
    return m_pipelineEntry.getInteger(-1);
  }

  /**
   * Gets the current recording status of the camera.
   *
   * @return True if the camera is recording, false otherwise.
   */
  public boolean getRecordingStatus() {
    if (m_recordStateEntry == null) {
      m_recordStateEntry = m_table.getEntry(kRecordStatusTopic);
    }
    assert m_recordStateEntry != null;
    return m_recordStateEntry.getBoolean(false);
  }

  /**
   * Sets the recording status of the camera.
   *
   * @param status True to start recording, false to stop.
   */
  public void setRecordStatus(boolean status) {
    if (m_recordStateEntry == null) {
      m_recordStateEntry = m_table.getEntry(kRecordStatusTopic);
    }
    assert m_recordStateEntry != null;
    m_recordStateEntry.setBoolean(status);
  }

  /**
   * Retrieves detection results of a given type from the default "results" key.
   *
   * @param clazz The class type of the results.
   * @param <T> The type parameter.
   * @return A list of detected results.
   * @throws IllegalArgumentException If the result type does not match the expected type.
   */
  public <T> List<T> getResults(Class<T> clazz) throws IllegalArgumentException {
    return getResults("results", clazz);
  }

  /**
   * Retrieves detection results with a specified key.
   *
   * @param resultsKey The key for retrieving results.
   * @param clazz The class type of the results.
   * @param <T> The type parameter.
   * @return A list of detected results.
   * @throws IllegalArgumentException If the result type does not match the expected type.
   */
  public <T> List<T> getResults(String resultsKey, Class<T> clazz) throws IllegalArgumentException {
    String jsonString = getDataEntry(resultsKey).getString("{\"data\":[],\"type\":\"\"}");

    if (jsonString.isEmpty() || jsonString.equals("{\"data\":[],\"type\":\"\"}")) {
      return new ArrayList<>();
    }

    ObjectMapper objectMapper =
        new ObjectMapper()
            .registerModule(new ParameterNamesModule())
            .registerModule(new Jdk8Module());
    try {
      Map<String, Object> resultMap = objectMapper.readValue(jsonString, new TypeReference<>() {});

      String actualTypeString = (String) resultMap.get("type");

      String requestedTypeString =
          registeredResultTypes.computeIfAbsent(
              clazz,
              c -> {
                if (c.isAnnotationPresent(RegisterSynapseResult.class)) {
                  return c.getAnnotation(RegisterSynapseResult.class).type();
                }
                throw new RuntimeException(
                    "Class " + c.getName() + " lacks @RegisterSynapseResult annotation.");
              });

      if (!actualTypeString.equals(requestedTypeString)) {
        throw new RuntimeException(
            "Type mismatch. Expected: " + requestedTypeString + ", but found: " + actualTypeString);
      }

      List<?> dataList = (List<?>) resultMap.get("data");

      return dataList.stream()
          .map(item -> objectMapper.convertValue(item, clazz))
          .collect(Collectors.toList());

    } catch (JsonProcessingException e) {
      e.printStackTrace();
    }
    return new ArrayList<>();
  }

  /**
   * Retrieves the camera ID.
   *
   * @return The camera ID.
   */
  public int getCameraID() {
    return m_id;
  }

  /**
   * Retrieves a specific entry from the camera's data table.
   *
   * @param dataKey The key of the data entry.
   * @return The NetworkTableEntry associated with the key.
   */
  private NetworkTableEntry getDataEntry(String dataKey) {
    return getDataResultsTable().getEntry(dataKey);
  }

  /**
   * Retrieves the data table for this camera.
   *
   * @return The NetworkTable representing the data table.
   */
  private NetworkTable getDataResultsTable() {
    if (m_dataTable == null) {
      m_dataTable = m_table.getSubTable("data");
    }
    assert m_dataTable != null;
    return m_dataTable;
  }

  /**
   * Retrieves the settings table for this camera.
   *
   * @return The NetworkTable representing the settings table.
   */
  private NetworkTable getSettingsTable() {
    if (m_settingsTable == null) {
      m_settingsTable = m_table.getSubTable("settings");
    }
    assert m_settingsTable != null;
    return m_settingsTable;
  }

  /**
   * Retrieves a setting value from the camera.
   *
   * @param key The setting key.
   * @return An Optional containing the setting value, if present.
   */
  public Optional<Object> getSetting(String key) {
    NetworkTableEntry entry = getSettingsTable().getEntry(key);
    if (!entry.exists()) return Optional.empty();

    return switch (entry.getType()) {
      case kDouble -> Optional.of(entry.getDouble(0.0));
      case kDoubleArray -> Optional.of(entry.getDoubleArray(new double[0]));
      case kString -> Optional.of(entry.getString(""));
      case kStringArray -> Optional.of(entry.getStringArray(new String[0]));
      case kInteger -> Optional.of(entry.getInteger(0));
      case kIntegerArray -> Optional.of(entry.getIntegerArray(new long[0]));
      default -> Optional.empty();
    };
  }

  /**
   * Sets a double setting value in the camera's settings table.
   *
   * @param key The setting key.
   * @param value The double value to set.
   * @throws RuntimeException If the setting type does not match.
   */
  public void setSetting(String key, double value) throws RuntimeException {
    NetworkTableEntry entry = getSettingsTable().getEntry(key);
    if (entry.getType() == NetworkTableType.kDouble) {
      entry.setDouble(value);
    } else {
      throwTypeMismatchException(key, entry.getType(), "double");
    }
  }

  /** Similar Javadoc applies for the other overloaded setSetting methods... */
  private void throwTypeMismatchException(String key, NetworkTableType actual, String expected) {
    throw new RuntimeException(
        String.format(
            "[Synapse]: Type mismatch for setting (%s). Expected: %s, but found: %s",
            key, expected, actual.toString()));
  }

  /**
   * Enum representing the camera setting keys. These keys are used to configure and retrieve
   * specific camera settings from a configuration system or camera interface.
   */
  public static enum CameraSettings {

    /** Key for controlling the camera's brightness setting. */
    kBrightness("brightness"),

    /** Key for controlling the camera's gain setting. */
    kGain("gain"),

    /** Key for controlling the camera's exposure setting. */
    kExposure("exposure"),

    /** Key for controlling the camera's orientation setting. */
    kOrientation("orientation");

    /** The key string representing the specific camera setting. */
    public final String key;

    /**
     * Constructor for the CameraSettings enum.
     *
     * @param key The string key associated with the camera setting.
     */
    CameraSettings(String key) {
      this.key = key;
    }
  }
}
