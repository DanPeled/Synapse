package synapse;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.io.IOException;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.Consumer;
import org.msgpack.jackson.dataformat.MessagePackFactory;
import org.wpilib.driverstation.DriverStationErrors;
import org.wpilib.math.geometry.Pose3d;
import org.wpilib.math.geometry.Transform3d;
import org.wpilib.networktables.BooleanSubscriber;
import org.wpilib.networktables.DoubleSubscriber;
import org.wpilib.networktables.GenericSubscriber;
import org.wpilib.networktables.IntegerSubscriber;
import org.wpilib.networktables.NetworkTable;
import org.wpilib.networktables.NetworkTableEntry;
import org.wpilib.networktables.NetworkTableInstance;
import org.wpilib.networktables.NetworkTableType;
import org.wpilib.networktables.NetworkTableValue;
import org.wpilib.networktables.RawSubscriber;
import org.wpilib.networktables.StringSubscriber;
import synapse.generated.SynapseApi;
import synapse.util.deserializers.WPILibGeometryModule;

/**
 * Represents a Synapse camera with fully cached NetworkTables entries, type-safe settings, and
 * methods for retrieving results and metrics.
 */
public class SynapseCamera implements AutoCloseable {

  /** Immutable snapshot of a setting topic's latest value. */
  record SettingValue(boolean valid, NetworkTableType type, Object value) {
    static SettingValue invalid() {
      return new SettingValue(false, null, null);
    }
  }

  /** Testable reader for a setting topic's latest value. */
  interface SettingReader extends AutoCloseable {
    SettingValue read();

    @Override
    void close();
  }

  /** Camera name */
  protected final String m_cameraName;

  /** Name of the Synapse NetworkTables table */
  public final String synapseTableName;

  /** Root table for this camera */
  protected NetworkTable m_table;

  /** Subtable containing camera settings */
  protected NetworkTable m_settingsTable;

  /** Full path of the settings subtable, usable without touching NetworkTables in tests. */
  protected String m_settingsTablePath;

  /** Subtable containing camera data/results */
  protected NetworkTable m_dataTable;

  /** Cache of NetworkTableEntries, keyed by full topic path to avoid cross-subtable collisions */
  protected final Map<String, NetworkTableEntry> m_entryCache = new ConcurrentHashMap<>();

  /** Latest-value readers for settings, keyed by full topic path */
  protected final Map<String, SettingReader> m_settingReaders = new ConcurrentHashMap<>();

  /** Setting keys for which a type mismatch has already been reported */
  protected final Set<String> m_warnedSettingKeys = ConcurrentHashMap.newKeySet();

  /** Reporter for setting type mismatches; overridable in tests. */
  protected Consumer<String> m_warningReporter =
      message -> DriverStationErrors.reportWarning(message, false);

  /** Entry used to publish the current pipeline ID */
  protected NetworkTableEntry m_pipelineEntry;

  /** Latest-value subscriber for the current pipeline ID */
  protected IntegerSubscriber m_pipelineSubscriber;

  /** Entry for storing or retrieving the camera's current pipeline type */
  protected StringSubscriber m_pipelineTypeSubscriber;

  /** Entry for storing the latest processing results from the camera */
  protected RawSubscriber m_resultsSubscriber;

  /** Entry used to publish the recording state */
  protected NetworkTableEntry m_recordStateEntry;

  /** Latest-value subscriber for the recording state */
  protected BooleanSubscriber m_recordStateSubscriber;

  /** Entry for tracking the latency of frame capture (in seconds) */
  protected DoubleSubscriber m_captureLatencySubscriber;

  /** Entry for tracking the latency of frame processing (in seconds) */
  protected DoubleSubscriber m_processLatencySubscriber;

  /**
   * ObjectMapper configured for MessagePack serialization/deserialization.
   *
   * <p>The WPILib geometry module lets custom result classes declare {@link Pose3d}, {@link
   * Transform3d}, and other geometry fields. Synapse sends those as plain arrays.
   */
  protected static final ObjectMapper s_ObjectMapper =
      new ObjectMapper(new MessagePackFactory()).registerModule(new WPILibGeometryModule());

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

      m_settingsTable = m_table.getSubTable(SynapseApi.SETTINGS_TABLE);
      m_settingsTablePath = m_settingsTable.getPath();
      m_dataTable = m_table.getSubTable(SynapseApi.DATA_TABLE);

      m_pipelineEntry = getCachedEntry(NetworkTableTopics.kPipelineTopic, m_table);
      m_recordStateEntry = getCachedEntry(NetworkTableTopics.kRecordStatusTopic, m_table);
      // Reads use latest-value subscribers so hot loops never call exists() or
      // getType() on an entry. Entries above remain for the setters only.
      m_pipelineSubscriber =
          m_table.getIntegerTopic(NetworkTableTopics.kPipelineTopic).subscribe(-1);
      m_recordStateSubscriber =
          m_table.getBooleanTopic(NetworkTableTopics.kRecordStatusTopic).subscribe(false);
      m_pipelineTypeSubscriber =
          m_table.getStringTopic(NetworkTableTopics.kPipelineTypeTopic).subscribe("Unknown");
      m_captureLatencySubscriber =
          m_table.getDoubleTopic(NetworkTableTopics.kCaptureLatencyTopic).subscribe(0.0);
      m_processLatencySubscriber =
          m_table.getDoubleTopic(NetworkTableTopics.kProcessLatencyTopic).subscribe(0.0);
      // The runtime publishes pipeline results under <camera>/data/results.
      m_resultsSubscriber =
          m_dataTable.getRawTopic(NetworkTableTopics.kResultsTopic).subscribe("raw", new byte[0]);
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
   * <p>The cache key includes the table path so identically named settings in different subtables
   * cannot share an entry.
   *
   * @param key the entry key
   * @param table the table to fetch the entry from
   * @return the cached or newly fetched NetworkTableEntry
   */
  public NetworkTableEntry getCachedEntry(String key, NetworkTable table) {
    return m_entryCache.computeIfAbsent(
        cacheKey(table.getPath(), key), ignored -> table.getEntry(key));
  }

  /**
   * Returns a latest-value reader for a setting topic, creating it once.
   *
   * @param key the setting key
   * @return the cached or newly created setting reader
   */
  protected SettingReader getSettingReader(String key) {
    return m_settingReaders.computeIfAbsent(
        cacheKey(settingsPath(), key),
        ignored ->
            new NetworkTablesSettingReader(getSettingsTable().getTopic(key).genericSubscribe()));
  }

  static String cacheKey(String tablePath, String key) {
    return tablePath + "/" + key;
  }

  private String settingsPath() {
    return m_settingsTablePath != null ? m_settingsTablePath : getSettingsTable().getPath();
  }

  /** Adapts a generic NetworkTables subscriber to a testable setting reader. */
  private static final class NetworkTablesSettingReader implements SettingReader {
    private final GenericSubscriber m_subscriber;

    private NetworkTablesSettingReader(GenericSubscriber subscriber) {
      m_subscriber = subscriber;
    }

    @Override
    public SettingValue read() {
      NetworkTableValue value = m_subscriber.get();
      if (!value.isValid()) return SettingValue.invalid();
      return new SettingValue(true, value.getType(), toObject(value));
    }

    @Override
    public void close() {
      m_subscriber.close();
    }
  }

  /**
   * Returns the current pipeline ID or -1 if unset.
   *
   * @return the pipeline index
   */
  public long getPipeline() {
    return m_pipelineSubscriber.get(-1);
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
    return m_recordStateSubscriber.get(false);
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
   * Returns the latest capture latency in seconds.
   *
   * @return capture latency in seconds, or 0 if it has not been published
   */
  public double getCaptureLatency() {
    return m_captureLatencySubscriber.get(0);
  }

  /**
   * Returns the latest processing latency in seconds.
   *
   * @return processing latency in seconds, or 0 if it has not been published
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
    SettingValue value = getSettingReader(key).read();
    if (!value.valid()) return Optional.empty();
    return Optional.ofNullable(value.value());
  }

  /**
   * Typed getter for camera settings.
   *
   * @param setting the typed setting
   * @param <T> the value type
   * @return Optional containing value if present and type matches
   */
  public <T> Optional<T> getSetting(Setting<T> setting) {
    SettingValue value = getSettingReader(setting.getKey()).read();
    if (!value.valid()) return Optional.empty();

    Object converted = value.value();
    if (converted == null || value.type() != setting.getNtType()) {
      warnMismatchOnce(setting, value.type(), converted);
      return Optional.empty();
    }

    if (!setting.getValueType().isInstance(converted)) {
      warnMismatchOnce(setting, value.type(), converted);
      return Optional.empty();
    }

    @SuppressWarnings("unchecked")
    T casted = (T) converted;
    return Optional.of(casted);
  }

  /** Converts a NetworkTables value to the Java type used by {@link Setting}. */
  static Object toObject(NetworkTableValue value) {
    return switch (value.getType()) {
      case DOUBLE -> value.getDouble();
      case DOUBLE_ARRAY -> value.getDoubleArray();
      case STRING -> value.getString();
      case STRING_ARRAY -> value.getStringArray();
      case INTEGER -> value.getInteger();
      case INTEGER_ARRAY -> value.getIntegerArray();
      case BOOLEAN -> value.getBoolean();
      case BOOLEAN_ARRAY -> value.getBooleanArray();
      default -> null;
    };
  }

  private <T> void warnMismatchOnce(Setting<T> setting, NetworkTableType actualType, Object value) {
    String warningKey = cacheKey(settingsPath(), setting.getKey());
    if (!m_warnedSettingKeys.add(warningKey)) return;

    m_warningReporter.accept(
        "[SynapseCamera] Type mismatch for key '"
            + setting.getKey()
            + "', expected "
            + setting.getNtType()
            + " ("
            + setting.getValueType().getSimpleName()
            + ") but received "
            + actualType
            + " ("
            + (value == null ? "null" : value.getClass().getSimpleName())
            + ")");
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

    /** The NetworkTableType corresponding to this setting (e.g., DOUBLE, STRING). */
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
      return new Setting<>(key, Double.class, NetworkTableType.DOUBLE);
    }

    /**
     * Creates a Setting representing an Integer (Long) value.
     *
     * @param key The key to use for this setting
     * @return A new Setting instance for Long values
     */
    public static Setting<Long> integerSetting(String key) {
      return new Setting<>(key, Long.class, NetworkTableType.INTEGER);
    }

    /**
     * Creates a Setting representing a String value.
     *
     * @param key The key to use for this setting
     * @return A new Setting instance for String values
     */
    public static Setting<String> stringSetting(String key) {
      return new Setting<>(key, String.class, NetworkTableType.STRING);
    }

    /**
     * Creates a Setting representing a double array value.
     *
     * @param key The key to use for this setting
     * @return A new Setting instance for double array values
     */
    public static Setting<double[]> doubleArraySetting(String key) {
      return new Setting<>(key, double[].class, NetworkTableType.DOUBLE_ARRAY);
    }

    /**
     * Creates a Setting representing a string array value.
     *
     * @param key The key to use for this setting
     * @return A new Setting instance for string array values
     */
    public static Setting<String[]> stringArraySetting(String key) {
      return new Setting<>(key, String[].class, NetworkTableType.STRING_ARRAY);
    }

    /**
     * Creates a Setting representing a boolean value.
     *
     * @param key The key to use for this setting
     * @return A new Setting instance for Boolean values
     */
    public static Setting<Boolean> booleanSetting(String key) {
      return new Setting<>(key, Boolean.class, NetworkTableType.BOOLEAN);
    }

    /**
     * Creates a Setting representing a long array value.
     *
     * @param key The key to use for this setting
     * @return A new Setting instance for long array values
     */
    public static Setting<long[]> integerArraySetting(String key) {
      return new Setting<>(key, long[].class, NetworkTableType.INTEGER_ARRAY);
    }

    /**
     * Creates a Setting representing a boolean array value.
     *
     * @param key The key to use for this setting
     * @return A new Setting instance for boolean array values
     */
    public static Setting<boolean[]> booleanArraySetting(String key) {
      return new Setting<>(key, boolean[].class, NetworkTableType.BOOLEAN_ARRAY);
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
    public static final Setting<Double> kBrightness = doubleSetting(SynapseApi.BRIGHTNESS_SETTING);

    /** Predefined setting for camera gain */
    public static final Setting<Double> kGain = doubleSetting(SynapseApi.GAIN_SETTING);

    /** Predefined setting for camera exposure */
    public static final Setting<Double> kExposure = doubleSetting(SynapseApi.EXPOSURE_SETTING);

    /** Predefined setting for camera orientation, in degrees (0, 90, 180, 270) */
    public static final Setting<Long> kOrientation = integerSetting(SynapseApi.ORIENTATION_SETTING);

    /** Predefined setting for camera contrast */
    public static final Setting<Double> kContrast = doubleSetting(SynapseApi.CONTRAST_SETTING);

    /** Predefined setting for camera saturation */
    public static final Setting<Double> kSaturation = doubleSetting(SynapseApi.SATURATION_SETTING);

    /** Predefined setting for camera hue */
    public static final Setting<Double> kHue = doubleSetting(SynapseApi.HUE_SETTING);

    /** Predefined setting for camera white balance temperature */
    public static final Setting<Double> kWhiteBalanceTemperature =
        doubleSetting(SynapseApi.WHITE_BALANCE_TEMPERATURE_SETTING);

    /** Predefined setting for camera sharpness */
    public static final Setting<Double> kSharpness = doubleSetting(SynapseApi.SHARPNESS_SETTING);
  }

  /** Standardized NetworkTables topic keys for pipelines, results, recording, and latency. */
  public static final class NetworkTableTopics {

    /** Topic for the current pipeline ID */
    public static final String kPipelineTopic = SynapseApi.PIPELINE;

    /** Topic for recording state */
    public static final String kRecordStatusTopic = SynapseApi.RECORD;

    /** Topic for the pipeline type string */
    public static final String kPipelineTypeTopic = SynapseApi.PIPELINE_TYPE;

    /** Topic for the camera view ID */
    public static final String kViewIDTopic = SynapseApi.VIEW_ID;

    /** Topic for results data */
    public static final String kResultsTopic = SynapseApi.RESULTS;

    /** Topic for camera capture latency (seconds) */
    public static final String kCaptureLatencyTopic = SynapseApi.CAPTURE_LATENCY;

    /** Topic for camera processing latency (seconds) */
    public static final String kProcessLatencyTopic = SynapseApi.PROCESS_LATENCY;

    /** Prevent instantiation */
    protected NetworkTableTopics() {}
  }

  @Override
  public void close() throws Exception {
    m_captureLatencySubscriber.close();
    m_processLatencySubscriber.close();
    m_pipelineTypeSubscriber.close();
    m_pipelineSubscriber.close();
    m_recordStateSubscriber.close();
    m_resultsSubscriber.close();
    m_settingReaders.values().forEach(SettingReader::close);
    m_settingReaders.clear();
    m_warnedSettingKeys.clear();
  }
}
