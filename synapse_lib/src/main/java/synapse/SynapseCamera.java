package synapse;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import edu.wpi.first.math.geometry.Pose3d;
import edu.wpi.first.math.geometry.Transform3d;
import edu.wpi.first.networktables.FloatSubscriber;
import edu.wpi.first.networktables.NetworkTable;
import edu.wpi.first.networktables.NetworkTableEntry;
import edu.wpi.first.networktables.NetworkTableInstance;
import edu.wpi.first.networktables.NetworkTableType;
import edu.wpi.first.networktables.PubSubOption;
import edu.wpi.first.networktables.RawSubscriber;
import edu.wpi.first.networktables.StringSubscriber;
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
public class SynapseCamera implements AutoCloseable {

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
  protected StringSubscriber m_pipelineTypeSubscriber;

  /** Entry for storing the latest processing results from the camera */
  protected RawSubscriber m_resultsSubscriber;

  /** Entry that indicates whether recording is currently active */
  protected NetworkTableEntry m_recordStateEntry;

  /** Entry for tracking the latency of frame capture (in milliseconds) */
  protected FloatSubscriber m_captureLatencySubscriber;

  /** Entry for tracking the latency of frame processing (in milliseconds) */
  protected FloatSubscriber m_processLatencySubscriber;

  /** ObjectMapper configured for MessagePack serialization/deserialization */
  protected static final ObjectMapper s_ObjectMapper = new ObjectMapper(new MessagePackFactory());

  /**
   * Transform representing the physical offset between the robot's coordinate frame and the
   * camera's coordinate frame.
   *
   * <p>This is used to convert between camera poses and robot poses, where the transform defines
   * the camera's position and orientation relative to the robot.
   */
  protected Transform3d m_robotToCameraOffset;

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

    if (!isJUnitTest()) {
      m_table =
          NetworkTableInstance.getDefault().getTable(synapseTableName).getSubTable(m_cameraName);

      m_pipelineEntry = getCachedEntry(NetworkTableTopics.kPipelineTopic, m_table);
      m_recordStateEntry = getCachedEntry(NetworkTableTopics.kRecordStatusTopic, m_table);
      m_pipelineTypeSubscriber =
          m_table
              .getStringTopic(NetworkTableTopics.kPipelineTypeTopic)
              .subscribe(
                  "Unknown", PubSubOption.keepDuplicates(true), PubSubOption.pollStorage(10));
      m_captureLatencySubscriber =
          m_table
              .getFloatTopic(NetworkTableTopics.kCaptureLatencyTopic)
              .subscribe(0, PubSubOption.keepDuplicates(true), PubSubOption.pollStorage(10));
      m_processLatencySubscriber =
          m_table
              .getFloatTopic(NetworkTableTopics.kProcessLatencyTopic)
              .subscribe(0, PubSubOption.keepDuplicates(true), PubSubOption.pollStorage(10));
      m_resultsSubscriber =
          m_table
              .getRawTopic(NetworkTableTopics.kResultsTopic)
              .subscribe(
                  "results",
                  new byte[0],
                  PubSubOption.keepDuplicates(true),
                  PubSubOption.pollStorage(10));
      m_settingsTable = m_table.getSubTable("settings");
      m_dataTable = m_table.getSubTable("data");
    }
  }

  /**
   * Sets the transform offset between the robot reference frame and the camera, and returns this
   * instance for chaining.
   *
   * <p>The offset defines where the camera is located relative to the robot, enabling conversion
   * between camera poses and robot poses.
   *
   * @param robotToCameraOffset the transform from robot space to camera space
   * @return this SynapseCamera instance for fluent chaining
   */
  public SynapseCamera withRobotToCameraOffset(Transform3d robotToCameraOffset) {
    m_robotToCameraOffset = robotToCameraOffset;
    return this;
  }

  /**
   * Assigns the transform offset between the robot and camera coordinate frames.
   *
   * <p>This offset is used when estimating robot pose based on camera pose measurements.
   *
   * @param robotToCameraOffset the transform from robot to camera
   */
  public void setRobotToCameraOffset(Transform3d robotToCameraOffset) {
    m_robotToCameraOffset = robotToCameraOffset;
  }

  /**
   * Returns the transform offset from the robot frame to the camera frame.
   *
   * @return the robot-to-camera Transform3d, or null if not configured
   */
  public Transform3d getRobotToCameraOffset() {
    return m_robotToCameraOffset;
  }

  /**
   * Converts a given camera pose into a robot pose using the configured robot-to-camera offset.
   *
   * <p>This performs the inverse transform of the stored offset and applies it to the camera pose,
   * yielding an estimated robot pose in the same coordinate frame.
   *
   * @param cameraPose the camera pose in a shared coordinate system
   * @return estimated robot pose
   * @throws NullPointerException if the offset has not been set
   */
  public Pose3d estimateRobotPose(Pose3d cameraPose) {
    return cameraPose.transformBy(m_robotToCameraOffset.inverse());
  }

  /**
   * Returns the settings subtable.
   *
   * @return the NetworkTable storing camera settings
   */
  protected NetworkTable getSettingsTable() {
    return m_settingsTable;
  }

  /**
   * Returns the data/results subtable.
   *
   * @return the NetworkTable storing camera results
   */
  protected NetworkTable getDataTable() {
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
    return m_pipelineEntry.getInteger(-1);
  }

  /**
   * Sets the current pipeline ID.
   *
   * @param pipeline pipeline index
   */
  public void setPipeline(long pipeline) {
    m_pipelineEntry.setInteger(pipeline);
  }

  /**
   * Returns the pipeline type string.
   *
   * @return the pipeline type
   */
  public String getPipelineType() {
    return m_pipelineTypeSubscriber.get("unknown");
  }

  /**
   * Returns whether the camera is currently recording.
   *
   * @return true if recording, false otherwise
   */
  public boolean getRecordingStatus() {
    return m_recordStateEntry.getBoolean(false);
  }

  /**
   * Sets the camera recording status.
   *
   * @param status true to start recording, false to stop
   */
  public void setRecordStatus(boolean status) {
    m_recordStateEntry.setBoolean(status);
  }

  /**
   * Returns the latest capture latency in milliseconds.
   *
   * @return capture latency
   */
  public double getCaptureLatency() {
    return m_captureLatencySubscriber.get(0);
  }

  /**
   * Returns the latest processing latency in milliseconds.
   *
   * @return processing latency
   */
  public double getProcessLatency() {
    return m_processLatencySubscriber.get(0);
  }

  /**
   * Deprecated untyped setting retrieval.
   *
   * @param key the setting key
   * @return an Optional containing the value if present
   */
  @Deprecated(forRemoval = true, since = "2025.0.1")
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
   * Returns the results subscriber.
   *
   * @return results subscriber
   */
  protected RawSubscriber getResultsSubscriber() {
    return m_resultsSubscriber;
  }

  /**
   * Deserialize results from serialized MessagePack data.
   *
   * @param <T> type of the result
   * @param typeref TypeReference describing the expected type
   * @param data serialized data
   * @return Optional containing deserialized results
   */
  public <T> Optional<T> deserializeResults(TypeReference<T> typeref, byte[] data) {
    try {
      return Optional.of(s_ObjectMapper.readValue(data, typeref));
    } catch (IOException e) {
      e.printStackTrace();
      return Optional.empty();
    }
  }

  /**
   * Retrieve and deserialize results from the given pipeline.
   *
   * <p>This method fetches the raw serialized results for the specified pipeline, and deserializes
   * them using the pipeline's associated TypeReference.
   *
   * @param <T> type of the result
   * @param pipelineType the pipeline type whose results are to be retrieved
   * @return Optional containing deserialized results if available, otherwise empty
   */
  public <T> Optional<T> getResults(SynapsePipelineType<T> pipelineType) {
    byte[] data = m_resultsSubscriber.get();
    if (data.length > 0) {
      return deserializeResults(pipelineType.getTypeReference(), data);
    } else {
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

  @Override
  public void close() throws Exception {
    m_captureLatencySubscriber.close();
    m_processLatencySubscriber.close();
    m_pipelineTypeSubscriber.close();
    m_resultsSubscriber.close();
  }
}
