package synapse.plugin;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.TimeUnit;
import javax.inject.Inject;
import org.gradle.api.DefaultTask;
import org.gradle.api.GradleException;
import org.gradle.api.tasks.TaskAction;

/** Starts the Synapse simulator process in the background. */
public abstract class SynapseSimStartTask extends DefaultTask {
  private final SynapseExtension synapse;

  @Inject
  public SynapseSimStartTask(SynapseExtension synapse) {
    this.synapse = synapse;
  }

  @TaskAction
  public void start() {
    if (!synapse.isSimEnabled()) {
      getLogger().lifecycle("Synapse simulation is disabled.");
      return;
    }

    synapse.validateForSim();

    if (synapse.isSimRunning()) {
      getLogger().lifecycle("Synapse simulator is already running.");
      return;
    }

    List<String> command = new ArrayList<>();
    command.add(synapse.getPythonExecutable());
    command.addAll(synapse.buildSimArguments());

    ProcessBuilder builder = new ProcessBuilder(command);
    builder.directory(synapse.getResolvedProjectDir());
    builder.redirectErrorStream(true);

    getLogger().lifecycle("Starting Synapse simulator: {}", String.join(" ", command));

    try {
      Process process = builder.start();
      Thread outputReader = startOutputReader(process);
      synapse.startSim(process, outputReader);
      synapse.registerShutdownHook(getLogger());

      if (process.waitFor(500, TimeUnit.MILLISECONDS)) {
        int exitCode = process.exitValue();
        synapse.stopSim(getLogger());
        throw new GradleException(
            "Synapse simulator exited immediately with code " + exitCode + ". See output above.");
      }
    } catch (IOException error) {
      throw new GradleException("Failed to start Synapse simulator: " + error.getMessage(), error);
    } catch (InterruptedException error) {
      Thread.currentThread().interrupt();
      synapse.stopSim(getLogger());
      throw new GradleException("Interrupted while starting Synapse simulator", error);
    }
  }

  private Thread startOutputReader(Process process) {
    Thread reader =
        new Thread(
            () -> {
              try (BufferedReader stream =
                  new BufferedReader(
                      new InputStreamReader(process.getInputStream(), StandardCharsets.UTF_8))) {
                String line;
                while ((line = stream.readLine()) != null) {
                  getLogger().lifecycle("[Synapse] {}", line);
                }
              } catch (IOException ignored) {
                // The process exited; nothing else to read.
              }
            },
            "synapse-sim-output");
    reader.setDaemon(true);
    reader.start();
    return reader;
  }
}
