package synapse;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import edu.wpi.first.networktables.NetworkTable;
import edu.wpi.first.networktables.NetworkTableEntry;
import edu.wpi.first.networktables.NetworkTableInstance;
import edu.wpi.first.networktables.NetworkTableType;
import edu.wpi.first.wpilibj.DriverStation;
import java.io.IOException;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;
import org.msgpack.jackson.dataformat.MessagePackFactory;

/**
 * Represents a Synapse camera with fully cached NetworkTables entries, type-safe settings, and
 * methods for retrieving results and metrics.
 */
public class SynapseCamera {

  /** Camera name */
  protected final String m_cameraName;

  /** Name of the Synapse NetworkTables table */
  public final String synapseTableName;

  /** Root table for this camera */
  protected NetworkTable m_table;

  /** Subtable containing camera settings */
  protected NetworkTable m_settingsTable;

  /** Subtable containing camera data/results */
  protected NetworkTable m_dataTable;

  /** Cache of all NetworkTableEntries for quick access */
  protected final Map<String, NetworkTableEntry> m_entryCache = new ConcurrentHashMap<>();

  /** Cached entry for the current pipeline ID */
  protected NetworkTableEntry m_pipelineEntry;

  /** Entry for storing or retrieving the camera's current pipeline type */
  protected NetworkTableEntry m_pipelineTypeEntry;

  /** Entry for storing the latest processing results from the camera */
  protected NetworkTableEntry m_resultsEntry;

  /** Entry that indicates whether recording is currently active */
  protected NetworkTableEntry m_recordStateEntry;

  /** Entry for tracking the latency of frame capture (in milliseconds) */
  protected NetworkTableEntry m_captureLatencyEntry;

  /** Entry for tracking the latency of frame processing (in milliseconds) */
  protected NetworkTableEntry m_processLatencyEntry;

  /** ObjectMapper configured for MessagePack serialization/deserialization */
  protected static final ObjectMapper s_ObjectMapper = new ObjectMapper(new MessagePackFactory());

  /**
   * Constructs a new SynapseCamera using the default coprocessor table name "Synapse".
   *
   * @param cameraName the camera's name
   */
  public SynapseCamera(String cameraName) {
    this(cameraName, "Synapse");
  }

  /**
   * Constructs a new SynapseCamera with a specific coprocessor table name.
   *
   * @param cameraName the camera's name
   * @param coprocessorName the NetworkTables root table for this camera
   */
  public SynapseCamera(String cameraName, String coprocessorName) {
    m_cameraName = cameraName;
    synapseTableName = coprocessorName;

    if (!isJUnitTest())
      m_table =
          NetworkTableInstance.getDefault().getTable(synapseTableName).getSubTable(m_cameraName);
  }

  /** Standardized NetworkTables topic keys for pipelines, results, recording, and latency. */
  public static final class NetworkTableTopics {

    /** Topic for the current pipeline ID */
    public static final String kPipelineTopic = "pipeline";

    /** Topic for recording state */
    public static final String kRecordStatusTopic = "record";

    /** Topic for the pipeline type string */
    public static final String kPipelineTypeTopic = "pipeline_type";

    /** Topic for results data */
    public static final String kResultsTopic = "results";

    /** Topic for camera capture latency (ms) */
    public static final String kCaptureLatencyTopic = "captureLatency";

    /** Topic for camera processing latency (ms) */
    public static final String kProcessLatencyTopic = "processLatency";

    /** Prevent instantiation */
    protected NetworkTableTopics() {}
  }

  /**
   * Returns the settings subtable.
   *
   * @return the NetworkTable storing camera settings
   */
  protected NetworkTable getSettingsTable() {
    if (m_settingsTable == null) {
      m_settingsTable = m_table.getSubTable("settings");
    }
    return m_settingsTable;
  }

  /**
   * Returns the data/results subtable.
   *
   * @return the NetworkTable storing camera results
   */
  protected NetworkTable getDataTable() {
    if (m_dataTable == null) {
      m_dataTable = m_table.getSubTable("data");
    }
    return m_dataTable;
  }

  /**
   * Retrieves a cached NetworkTableEntry for a given key.
   *
   * @param key the entry key
   * @param table the table to fetch the entry from
   * @return the cached or newly fetched NetworkTableEntry
   */
  public NetworkTableEntry getCachedEntry(String key, NetworkTable table) {
    return m_entryCache.computeIfAbsent(key, table::getEntry);
  }

  /**
   * Returns the current pipeline ID or -1 if unset.
   *
   * @return the pipeline index
   */
  public long getPipeline() {
    if (m_pipelineEntry == null)
      m_pipelineEntry = getCachedEntry(NetworkTableTopics.kPipelineTopic, m_table);
    return m_pipelineEntry.getInteger(-1);
  }

  /**
   * Sets the current pipeline ID.
   *
   * @param pipeline pipeline index
   */
  public void setPipeline(long pipeline) {
    if (m_pipelineEntry == null)
      m_pipelineEntry = getCachedEntry(NetworkTableTopics.kPipelineTopic, m_table);
    m_pipelineEntry.setInteger(pipeline);
  }

  /**
   * Returns the pipeline type string.
   *
   * @return the pipeline type
   */
  public String getPipelineType() {
    if (m_pipelineTypeEntry == null)
      m_pipelineTypeEntry = getCachedEntry(NetworkTableTopics.kPipelineTypeTopic, m_table);
    return m_pipelineTypeEntry.getString("unknown");
  }

  /**
   * Returns whether the camera is currently recording.
   *
   * @return true if recording, false otherwise
   */
  public boolean getRecordingStatus() {
    if (m_recordStateEntry == null)
      m_recordStateEntry = getCachedEntry(NetworkTableTopics.kRecordStatusTopic, m_table);
    return m_recordStateEntry.getBoolean(false);
  }

  /**
   * Sets the camera recording status.
   *
   * @param status true to start recording, false to stop
   */
  public void setRecordStatus(boolean status) {
    if (m_recordStateEntry == null)
      m_recordStateEntry = getCachedEntry(NetworkTableTopics.kRecordStatusTopic, m_table);
    m_recordStateEntry.setBoolean(status);
  }

  /**
   * Returns the latest capture latency in milliseconds.
   *
   * @return capture latency
   */
  public double getCaptureLatency() {
    if (m_captureLatencyEntry == null)
      m_captureLatencyEntry = getCachedEntry(NetworkTableTopics.kCaptureLatencyTopic, m_table);
    return m_captureLatencyEntry.getDouble(-1);
  }

  /**
   * Returns the latest processing latency in milliseconds.
   *
   * @return processing latency
   */
  public double getProcessLatency() {
    if (m_processLatencyEntry == null)
      m_processLatencyEntry = getCachedEntry(NetworkTableTopics.kProcessLatencyTopic, m_table);
    return m_processLatencyEntry.getDouble(-1);
  }

  /**
   * Deprecated untyped setting retrieval.
   *
   * @param key the setting key
   * @return an Optional containing the value if present
   */
  @Deprecated(forRemoval = true, since = "2025.0.0b4")
  public Optional<Object> getSetting(String key) {
    NetworkTableEntry entry = getCachedEntry(key, getSettingsTable());
    if (!entry.exists()) return Optional.empty();

    return switch (entry.getType()) {
      case kDouble -> Optional.of(entry.getDouble(0.0));
      case kDoubleArray -> Optional.of(entry.getDoubleArray(new double[0]));
      case kString -> Optional.of(entry.getString(""));
      case kStringArray -> Optional.of(entry.getStringArray(new String[0]));
      case kInteger -> Optional.of(entry.getInteger(0));
      case kIntegerArray -> Optional.of(entry.getIntegerArray(new long[0]));
      case kBoolean -> Optional.of(entry.getBoolean(false));
      case kBooleanArray -> Optional.of(entry.getBooleanArray(new boolean[0]));
      default -> Optional.empty();
    };
  }

  /**
   * Typed getter for camera settings.
   *
   * @param setting the typed setting
   * @param <T> the value type
   * @return Optional containing value if present and type matches
   */
  public <T> Optional<T> getSetting(Setting<T> setting) {
    NetworkTableEntry entry = getCachedEntry(setting.getKey(), getSettingsTable());

    if (!entry.exists()) return Optional.empty();

    Object value =
        switch (entry.getType()) {
          case kDouble -> entry.getDouble(0.0);
          case kDoubleArray -> entry.getDoubleArray(new double[0]);
          case kString -> entry.getString("");
          case kStringArray -> entry.getStringArray(new String[0]);
          case kInteger -> entry.getInteger(0);
          case kIntegerArray -> entry.getIntegerArray(new long[0]);
          case kBoolean -> entry.getBoolean(false);
          case kBooleanArray -> entry.getBooleanArray(new boolean[0]);
          default -> {
            DriverStation.reportWarning(
                "[SynapseCamera] Unsupported NT type for key '" + setting.getKey() + "'", false);
            yield null;
          }
        };

    if (value == null
        || !setting.getValueType().isInstance(value)
        || !setting.getNtType().equals(entry.getType())) {
      DriverStation.reportWarning(
          "[SynapseCamera] Type mismatch for key '"
              + setting.getKey()
              + "', expected "
              + setting.getValueType().getSimpleName()
              + " but received "
              + (value == null ? "null" : value.getClass().getSimpleName()),
          false);
      return Optional.empty();
    }

    @SuppressWarnings("unchecked")
    T casted = (T) value;
    return Optional.of(casted);
  }

  /**
   * Typed setter for camera settings.
   *
   * @param setting the typed setting
   * @param value the value to set
   * @param <T> type of the value
   */
  public <T> void setSetting(Setting<T> setting, T value) {
    NetworkTableEntry entry = getCachedEntry(setting.getKey(), getSettingsTable());
    if (!entry.exists() || entry.getType() == setting.getNtType()) {
      entry.setValue(value);
      return;
    }

    throw new RuntimeException(
        String.format(
            "[SynapseCamera]: Type mismatch for setting '%s'. Expected: %s, but found: %s",
            setting.getKey(), setting.getNtType(), entry.getType()));
  }

  /**
   * Returns the results entry.
   *
   * @return cached results NetworkTableEntry
   */
  protected NetworkTableEntry getResultsEntry() {
    if (m_resultsEntry == null) {
      m_resultsEntry = getCachedEntry(NetworkTableTopics.kResultsTopic, getDataTable());
    }
    return m_resultsEntry;
  }

  /**
   * Deserialize results from serialized MessagePack data.
   *
   * @param <T> type of the result
   * @param typeref TypeReference describing the expected type
   * @param data serialized data
   * @return Optional containing deserialized results
   */
  public <T> Optional<T> getResults(TypeReference<T> typeref, byte[] data) {
    try {
      return Optional.of(s_ObjectMapper.readValue(data, typeref));
    } catch (IOException e) {
      e.printStackTrace();
      return Optional.empty();
    }
  }

  /**
   * Returns the camera name.
   *
   * @return camera name
   */
  public String getCameraName() {
    return m_cameraName;
  }

  /**
   * Checks whether the current execution is in a JUnit or TestNG test.
   *
   * @return true if running inside a test framework
   */
  public static boolean isJUnitTest() {
    for (StackTraceElement element : Thread.currentThread().getStackTrace()) {
      String className = element.getClassName();
      if (className.startsWith("org.junit.")
          || className.startsWith("org.junit.jupiter.")
          || className.startsWith("org.testng.")) {
        return true;
      }
    }
    return false;
  }

  /**
   * Represents a typed Synapse setting that can be stored in a NetworkTable.
   *
   * @param <T> The type of the setting value (e.g., Double, String, arrays, etc.)
   */
  public static final class Setting<T> {

    /** The key used to identify this setting in the NetworkTable. */
    protected final String key;

    /** The Java class of the value type for this setting. */
    protected final Class<T> valueType;

    /** The NetworkTableType corresponding to this setting (e.g., kDouble, kString). */
    protected final NetworkTableType ntType;

    /**
     * Constructs a new Setting.
     *
     * @param key The key used to store this setting in the NetworkTable
     * @param valueType The Java type of the setting value
     * @param ntType The NetworkTableType corresponding to this setting
     */
    protected Setting(String key, Class<T> valueType, NetworkTableType ntType) {
      this.key = key;
      this.valueType = valueType;
      this.ntType = ntType;
    }

    /**
     * @return The key for this setting
     */
    public String getKey() {
      return key;
    }

    /**
     * @return The Java class type of this setting's value
     */
    public Class<T> getValueType() {
      return valueType;
    }

    /**
     * @return The NetworkTableType of this setting
     */
    public NetworkTableType getNtType() {
      return ntType;
    }

    /**
     * Creates a Setting representing a Double value.
     *
     * @param key The key to use for this setting
     * @return A new Setting instance for Double values
     */
    public static Setting<Double> doubleSetting(String key) {
      return new Setting<>(key, Double.class, NetworkTableType.kDouble);
    }

    /**
     * Creates a Setting representing an Integer (Long) value.
     *
     * @param key The key to use for this setting
     * @return A new Setting instance for Long values
     */
    public static Setting<Long> integerSetting(String key) {
      return new Setting<>(key, Long.class, NetworkTableType.kInteger);
    }

    /**
     * Creates a Setting representing a String value.
     *
     * @param key The key to use for this setting
     * @return A new Setting instance for String values
     */
    public static Setting<String> stringSetting(String key) {
      return new Setting<>(key, String.class, NetworkTableType.kString);
    }

    /**
     * Creates a Setting representing a double array value.
     *
     * @param key The key to use for this setting
     * @return A new Setting instance for double array values
     */
    public static Setting<double[]> doubleArraySetting(String key) {
      return new Setting<>(key, double[].class, NetworkTableType.kDoubleArray);
    }

    /**
     * Creates a Setting representing a string array value.
     *
     * @param key The key to use for this setting
     * @return A new Setting instance for string array values
     */
    public static Setting<String[]> stringArraySetting(String key) {
      return new Setting<>(key, String[].class, NetworkTableType.kStringArray);
    }

    /**
     * Creates a generic Setting with a custom type and NetworkTableType.
     *
     * @param key The key for this setting
     * @param type The Java class of the value type
     * @param ntType The NetworkTableType corresponding to the value type
     * @param <T> The type of the setting value
     * @return A new generic Setting instance
     */
    public static <T> Setting<T> generic(String key, Class<T> type, NetworkTableType ntType) {
      return new Setting<>(key, type, ntType);
    }

    /** Predefined setting for camera brightness */
    public static final Setting<Double> kBrightness = doubleSetting("brightness");

    /** Predefined setting for camera gain */
    public static final Setting<Double> kGain = doubleSetting("gain");

    /** Predefined setting for camera exposure */
    public static final Setting<Double> kExposure = doubleSetting("exposure");

    /** Predefined setting for camera orientation */
    public static final Setting<String> kOrientation = stringSetting("orientation");
  }
}
