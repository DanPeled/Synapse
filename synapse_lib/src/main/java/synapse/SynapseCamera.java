package synapse;

import com.fasterxml.jackson.core.exc.StreamReadException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.DatabindException;
import com.fasterxml.jackson.databind.ObjectMapper;
import edu.wpi.first.networktables.NetworkTable;
import edu.wpi.first.networktables.NetworkTableEntry;
import edu.wpi.first.networktables.NetworkTableInstance;
import edu.wpi.first.networktables.NetworkTableType;
import java.io.IOException;
import java.util.Optional;
import org.msgpack.jackson.dataformat.MessagePackFactory;

// import synapse.util.deserializers.WPILibGeometryModule;

/**
 * Represents a camera in the Synapse system, providing methods to manage
 * settings and retrieve
 * results from NetworkTables.
 */
public class SynapseCamera {
  /**
   * A container class holding the standard NetworkTables topic keys used for
   * communication between
   * Synapse and coprocessors.
   *
   * <p>
   * These constants define the names of NetworkTables topics for pipeline
   * configuration, status
   * reporting, and result data.
   */
  public static class NetworkTableTopics {
    /** The topic for pipeline-related data. */
    public static final String kPipelineTopic = "pipeline";

    /** The topic for recording status. */
    public static final String kRecordStatusTopic = "record";

    /** The topic for pipeline type. */
    public static final String kPipelineTypeTopic = "pipeline_type";

    /** The topic for results data. */
    public static final String kResultsTopic = "results";

    /** The topic for capture latency. */
    public static final String kCaptureLatencyTopic = "captureLatency";

    /** The topic for processing latency. */
    public static final String kProcessLatencyTopic = "processLatency";

    /** Prevents instantiation. */
    private NetworkTableTopics() {
    }
  }

  /** Jackson ObjectMapper configured for MessagePack and WPILib geometry. */
  private static final ObjectMapper s_ObjectMapper = createMapper();

  /** The name of the Synapse table in the NetworkTables */
  public final String synapseTableName;

  /** Unique identifier for this SynapseCamera instance */
  private final String m_cameraName;

  /** Main NetworkTable instance for this camera. */
  private NetworkTable m_table;

  /** Subtable storing detection and result data. */
  private NetworkTable m_dataTable;

  /** Subtable storing camera and pipeline settings. */
  private NetworkTable m_settingsTable;

  /** NetworkTableEntry representing the selected vision processing pipeline. */
  private NetworkTableEntry m_pipelineEntry;

  /** NetworkTableEntry storing the pipeline type string. */
  private NetworkTableEntry m_pipelineTypeEntry;

  /** NetworkTableEntry storing the raw results data. */
  private NetworkTableEntry m_resultsTopic;

  /** NetworkTableEntry representing the camera's recording status. */
  private NetworkTableEntry m_recordStateEntry;

  /** NetworkTableEntry representing the camera's capture latency (ms). */
  private NetworkTableEntry m_captureLatencyEntry;

  /** NetworkTableEntry representing the camera's processing latency (ms). */
  private NetworkTableEntry m_processLatencyEntry;

  /**
   * Constructs a new {@code SynapseCamera} instance with the given camera name.
   * Uses the default
   * coprocessor name {@code "Synapse"}.
   *
   * @param cameraName the camera's name
   */
  public SynapseCamera(String cameraName) {
    this(cameraName, "Synapse");
  }

  /**
   * Constructs a new {@code SynapseCamera} instance with the given camera name
   * and coprocessor
   * name.
   *
   * @param cameraName      the camera's name
   * @param coprocessorName the coprocessor table name
   */
  public SynapseCamera(String cameraName, String coprocessorName) {
    m_cameraName = cameraName;
    synapseTableName = coprocessorName;

    if (!isJUnitTest()) { // JUnit crashes ntcore for some reason
      m_table = NetworkTableInstance.getDefault().getTable(synapseTableName).getSubTable(m_cameraName);
    }
  }

  /**
   * Sets the camera pipeline ID.
   *
   * @param pipeline The pipeline ID to set.
   */
  public void setPipeline(long pipeline) {
    if (m_pipelineEntry == null) {
      m_pipelineEntry = m_table.getEntry(NetworkTableTopics.kPipelineTopic);
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
      m_pipelineEntry = m_table.getEntry(NetworkTableTopics.kPipelineTopic);
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
      m_recordStateEntry = m_table.getEntry(NetworkTableTopics.kRecordStatusTopic);
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
      m_recordStateEntry = m_table.getEntry(NetworkTableTopics.kRecordStatusTopic);
    }
    assert m_recordStateEntry != null;
    m_recordStateEntry.setBoolean(status);
  }

  /**
   * Retrieves the camera name.
   *
   * @return The camera name.
   */
  public String getCameraName() {
    return m_cameraName;
  }

  /**
   * Fetches and deserializes the results for a given SynapsePipeline in a
   * type-safe way.
   *
   * @param pipeline The SynapsePipeline to fetch results from.
   * @param <T>      The expected result type of the pipeline.
   * @return The deserialized result.
   * @throws IOException if reading or deserialization fails.
   */
  public <T> T getResults(SynapsePipeline<T> pipeline) throws IOException {
    return getResults(pipeline.getTypeReference(), pipeline.typestring);
  }

  /**
   * Fetches and deserializes data from the NetworkTables results topic into the
   * specified type.
   *
   * @param <T>        The type of the object to deserialize.
   * @param typeref    The TypeReference describing the target type.
   * @param typestring The expected pipeline type string; used to validate the
   *                   entry.
   * @return An object of type {@code T}, deserialized from the raw NetworkTables
   *         data.
   * @throws StreamReadException If the input stream cannot be read properly.
   * @throws DatabindException   If there is a problem mapping the JSON bytes to
   *                             the target type.
   * @throws IOException         If there is a low-level I/O problem accessing the
   *                             NetworkTables data.
   */
  public <T> T getResults(TypeReference<T> typeref, String typestring)
      throws StreamReadException, DatabindException, IOException {
    if (m_resultsTopic == null) {
      m_resultsTopic = getDataEntry(NetworkTableTopics.kResultsTopic);
    }
    if (m_resultsTopic == null) {
      throw new IllegalStateException("Results topic is null");
    }
    if (!getPipelineType().equals(typestring)) {
      throw new IllegalArgumentException(
          "Pipeline type mismatch: expected " + typestring + " but got " + getPipelineType());
    }

    byte[] data = m_resultsTopic.getRaw(new byte[0]);
    return getResults(typeref, data);
  }

  /**
   * Deserializes the given byte array into an object of the specified type.
   *
   * <p>
   * This method supports both JSON and MessagePack formats, depending on the
   * configured
   * ObjectMapper.
   *
   * @param <T>     The type of the result object.
   * @param typeref The TypeReference describing the expected type of the result.
   * @param data    The serialized data as a byte array.
   * @return An instance of type T deserialized from the provided data.
   * @throws StreamReadException If there is a low-level I/O or format problem
   *                             while reading.
   * @throws DatabindException   If there is a problem mapping the data to the
   *                             specified type.
   * @throws IOException         If a general I/O error occurs during
   *                             deserialization.
   */
  public <T> T getResults(TypeReference<T> typeref, byte[] data)
      throws StreamReadException, DatabindException, IOException {
    return s_ObjectMapper.readValue(data, typeref);
  }

  /**
   * Gets the pipeline type string from the camera.
   *
   * @return The pipeline type string; "unknown" if not set.
   */
  public String getPipelineType() {
    if (m_pipelineTypeEntry == null) {
      m_pipelineTypeEntry = m_table.getEntry(NetworkTableTopics.kPipelineTypeTopic);
    }
    assert m_pipelineTypeEntry != null;
    return m_pipelineTypeEntry.getString("unknown");
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
    if (!entry.exists())
      return Optional.empty();

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
   * @param key   The setting key.
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

  /**
   * Throws a standardized runtime exception for type mismatches.
   *
   * @param key      The setting key.
   * @param actual   The actual NetworkTableType found.
   * @param expected The expected type as a string.
   */
  private void throwTypeMismatchException(String key, NetworkTableType actual, String expected) {
    throw new RuntimeException(
        String.format(
            "[Synapse]: Type mismatch for setting (%s). Expected: %s, but found: %s",
            key, expected, actual.toString()));
  }

  /**
   * Creates and configures the ObjectMapper for MessagePack and WPILib geometry
   * support.
   *
   * @return A configured ObjectMapper instance.
   */
  private static ObjectMapper createMapper() {
    ObjectMapper mapper = new ObjectMapper(new MessagePackFactory());
    // mapper.registerModule(new WPILibGeometryModule());
    return mapper;
  }

  /**
   * Gets the latest capture latency from the camera in milliseconds.
   *
   * @return The capture latency, or -1 if not available.
   */
  public double getCaptureLatency() {
    if (m_captureLatencyEntry == null) {
      m_captureLatencyEntry = m_table.getEntry(NetworkTableTopics.kCaptureLatencyTopic);
    }
    return m_captureLatencyEntry.getDouble(-1);
  }

  /**
   * Gets the latest processing latency from the camera in milliseconds.
   *
   * @return The processing latency, or -1 if not available.
   */
  public double getProcessLatency() {
    if (m_processLatencyEntry == null) {
      m_processLatencyEntry = m_table.getEntry(NetworkTableTopics.kProcessLatencyTopic);
    }
    return m_processLatencyEntry.getDouble(-1);
  }

  /**
   * Enum representing the camera setting keys. These keys are used to configure
   * and retrieve
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

  /**
   * Checks if the current code is running inside a unit test framework.
   *
   * <p>
   * This method inspects the current thread's stack trace and looks for class
   * names associated
   * with popular test frameworks, such as JUnit 4/5 and TestNG. If any stack
   * frame indicates that a
   * test framework is active, it returns {@code true}.
   *
   * @return {@code true} if the current code is executing inside a unit test,
   *         {@code false}
   *         otherwise
   */
  public static boolean isJUnitTest() {
    for (StackTraceElement element : Thread.currentThread().getStackTrace()) {
      String className = element.getClassName();
      if (className.startsWith("org.junit.") // JUnit 4 internal
          || className.startsWith("org.junit.jupiter.") // JUnit 5
          || className.startsWith("org.testng.")) { // Optional: TestNG
        return true;
      }
    }
    return false;
  }
}
