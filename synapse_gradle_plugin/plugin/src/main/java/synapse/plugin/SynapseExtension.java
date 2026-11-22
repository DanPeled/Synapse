package synapse.plugin;

import java.io.File;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.concurrent.TimeUnit;
import org.gradle.api.GradleException;
import org.gradle.api.Project;
import org.gradle.api.logging.Logger;

/** Configuration shared by the Synapse deploy and simulation tasks. */
public class SynapseExtension {
  private static final String MARKER_FILE = ".synapseproject";

  private final Project project;
  private String projectName = "synapseproject";
  private String projectDir;
  private String mainScript = "main.py";
  private String pythonExecutable = defaultPythonExecutable();
  private String deviceName;
  private final List<String> devices = new ArrayList<>();
  private boolean installDependencies;
  private boolean followLogs;
  private boolean dryRun;
  private boolean enabled = true;
  private boolean simEnabled = true;
  private boolean headless = true;

  private Process simProcess;
  private Thread simOutputThread;
  private boolean shutdownHookRegistered;

  public SynapseExtension(Project project) {
    this.project = project;
  }

  /**
   * Directory name of the Synapse coprocessor project, relative to the robot project or its root.
   */
  public String getProjectName() {
    return projectName;
  }

  public void setProjectName(String projectName) {
    this.projectName = projectName;
  }

  /** Explicit path to the Synapse project. Overrides {@link #getProjectName()}. */
  public String getProjectDir() {
    return projectDir;
  }

  public void setProjectDir(Object projectDir) {
    this.projectDir = projectDir == null ? null : projectDir.toString();
  }

  /** Entry point run in simulation mode. Defaults to {@code main.py}. */
  public String getMainScript() {
    return mainScript;
  }

  public void setMainScript(String mainScript) {
    this.mainScript = mainScript;
  }

  /** Python interpreter used to invoke the Synapse runtime and installer. */
  public String getPythonExecutable() {
    return pythonExecutable;
  }

  public void setPythonExecutable(String pythonExecutable) {
    this.pythonExecutable = pythonExecutable;
  }

  /** Single device name, retained for compatibility with the original plugin API. */
  public String getDeviceName() {
    return deviceName;
  }

  public void setDeviceName(String deviceName) {
    this.deviceName = deviceName;
  }

  /** Additional device names. An empty list deploys to every configured device. */
  public List<String> getDevices() {
    return devices;
  }

  public void setDevices(Iterable<String> devices) {
    this.devices.clear();
    if (devices != null) {
      for (String device : devices) {
        this.devices.add(device);
      }
    }
  }

  /** Run {@code synapse_installer install} instead of {@code deploy}. */
  public boolean isInstallDependencies() {
    return installDependencies;
  }

  public void setInstallDependencies(boolean installDependencies) {
    this.installDependencies = installDependencies;
  }

  /** Follow runtime logs after deployment. Disabled by default so Gradle can finish. */
  public boolean isFollowLogs() {
    return followLogs;
  }

  public void setFollowLogs(boolean followLogs) {
    this.followLogs = followLogs;
  }

  /** Pass {@code --dry-run} to the installer. */
  public boolean isDryRun() {
    return dryRun;
  }

  public void setDryRun(boolean dryRun) {
    this.dryRun = dryRun;
  }

  /** Disable all Synapse tasks. */
  public boolean isEnabled() {
    return enabled;
  }

  public void setEnabled(boolean enabled) {
    this.enabled = enabled;
  }

  /** Start the Synapse simulator with robot simulation. */
  public boolean isSimEnabled() {
    return simEnabled;
  }

  public void setSimEnabled(boolean simEnabled) {
    this.simEnabled = simEnabled;
  }

  /** Pass {@code --headless} to the Synapse runtime in simulation. */
  public boolean isHeadless() {
    return headless;
  }

  public void setHeadless(boolean headless) {
    this.headless = headless;
  }

  /** Resolves the configured Synapse project directory. */
  public File getResolvedProjectDir() {
    String value = projectDir != null && !projectDir.isBlank() ? projectDir : projectName;
    if (value == null || value.isBlank()) {
      throw new GradleException("synapse.projectName or synapse.projectDir must be set");
    }

    File fromProject = project.file(value);
    if (new File(value).isAbsolute()) {
      return fromProject;
    }

    File fromRoot = new File(project.getRootDir(), value);
    if (new File(fromRoot, MARKER_FILE).isFile()) {
      return fromRoot;
    }
    return fromProject;
  }

  /** Validates that deployment can run from the configured project. */
  public void validateForDeploy() {
    File dir = getResolvedProjectDir();
    if (!new File(dir, MARKER_FILE).isFile()) {
      throw new GradleException(
          "Synapse project is missing "
              + MARKER_FILE
              + ": "
              + dir
              + ". Set synapse.projectName or synapse.projectDir to the coprocessor project.");
    }
  }

  /** Validates that simulation can run from the configured project. */
  public void validateForSim() {
    validateForDeploy();
    File script = getMainScriptFile();
    if (!script.isFile()) {
      throw new GradleException("Synapse simulation entry point does not exist: " + script);
    }
  }

  /** Returns the simulator entry point path. */
  public File getMainScriptFile() {
    return new File(getResolvedProjectDir(), mainScript);
  }

  /** Builds the installer arguments, excluding the Python interpreter. */
  public List<String> buildDeployArguments() {
    List<String> arguments = new ArrayList<>();
    arguments.add("-m");
    arguments.add("synapse_installer");
    arguments.add(installDependencies ? "install" : "deploy");
    // Gradle builds are non-interactive, so never wait for a confirmation prompt.
    arguments.add("--yes");
    if (!followLogs) {
      arguments.add("--no-logs");
    }
    if (dryRun) {
      arguments.add("--dry-run");
    }
    arguments.addAll(getDeploymentDevices());
    return arguments;
  }

  /** Builds the runtime arguments, excluding the Python interpreter. */
  public List<String> buildSimArguments() {
    List<String> arguments = new ArrayList<>();
    arguments.add(getMainScriptFile().getAbsolutePath());
    arguments.add("--sim");
    if (headless) {
      arguments.add("--headless");
    }
    return arguments;
  }

  /** Returns the deduplicated list of devices selected for deployment. */
  public List<String> getDeploymentDevices() {
    Set<String> selected = new LinkedHashSet<>();
    if (deviceName != null && !deviceName.isBlank()) {
      selected.add(deviceName.trim());
    }
    for (String device : devices) {
      if (device != null && !device.isBlank()) {
        selected.add(device.trim());
      }
    }
    return new ArrayList<>(selected);
  }

  /** Returns true while a simulator process launched by this extension is alive. */
  public synchronized boolean isSimRunning() {
    return simProcess != null && simProcess.isAlive();
  }

  /** Records the running simulator process and its output reader. */
  public synchronized void startSim(Process process, Thread outputReader) {
    if (isSimRunning()) {
      throw new GradleException("A Synapse simulator process is already running");
    }
    simProcess = process;
    simOutputThread = outputReader;
  }

  /** Stops the simulator process, including any child processes. */
  public synchronized void stopSim(Logger logger) {
    Process process = simProcess;
    if (process == null) {
      return;
    }

    if (process.isAlive()) {
      logger.lifecycle("Stopping Synapse simulator (pid {})", process.pid());
      destroyProcessTree(process, false);
      try {
        if (!process.waitFor(5, TimeUnit.SECONDS)) {
          destroyProcessTree(process, true);
          process.waitFor(2, TimeUnit.SECONDS);
        }
      } catch (InterruptedException error) {
        Thread.currentThread().interrupt();
        destroyProcessTree(process, true);
      }
    }

    Thread outputReader = simOutputThread;
    if (outputReader != null) {
      try {
        outputReader.join(1000);
      } catch (InterruptedException error) {
        Thread.currentThread().interrupt();
      }
    }

    simProcess = null;
    simOutputThread = null;
  }

  /** Registers a JVM shutdown hook so Ctrl+C cannot orphan the simulator. */
  public synchronized void registerShutdownHook(Logger logger) {
    if (shutdownHookRegistered) {
      return;
    }
    Runtime.getRuntime().addShutdownHook(new Thread(() -> stopSim(logger), "synapse-sim-shutdown"));
    shutdownHookRegistered = true;
  }

  private static void destroyProcessTree(Process process, boolean force) {
    process
        .descendants()
        .forEach(handle -> {
          if (force) {
            handle.destroyForcibly();
          } else {
            handle.destroy();
          }
        });
    if (force) {
      process.destroyForcibly();
    } else {
      process.destroy();
    }
  }

  private static String defaultPythonExecutable() {
    String os = System.getProperty("os.name", "").toLowerCase(Locale.ROOT);
    return os.contains("win") ? "python" : "python3";
  }
}
