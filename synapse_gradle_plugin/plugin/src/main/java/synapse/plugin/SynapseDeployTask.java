package synapse.plugin;

import java.util.ArrayList;
import java.util.List;
import javax.inject.Inject;
import org.gradle.api.DefaultTask;
import org.gradle.api.tasks.TaskAction;
import org.gradle.process.ExecOperations;

/** Deploys the Synapse coprocessor project with the current installer CLI. */
public abstract class SynapseDeployTask extends DefaultTask {
  private final SynapseExtension synapse;

  @Inject
  public SynapseDeployTask(SynapseExtension synapse) {
    this.synapse = synapse;
  }

  @Inject
  protected abstract ExecOperations getExecOperations();

  @TaskAction
  public void deploy() {
    if (!synapse.isEnabled()) {
      getLogger().lifecycle("Synapse deployment is disabled.");
      return;
    }

    synapse.validateForDeploy();

    List<String> command = new ArrayList<>();
    command.add(synapse.getPythonExecutable());
    command.addAll(synapse.buildDeployArguments());

    getLogger()
        .lifecycle(
            "Deploying Synapse project {} to {}",
            synapse.getResolvedProjectDir(),
            synapse.getDeploymentDevices().isEmpty()
                ? "all configured devices"
                : synapse.getDeploymentDevices());

    getExecOperations()
        .exec(spec -> {
          spec.setWorkingDir(synapse.getResolvedProjectDir());
          spec.commandLine(command);
        });
  }
}
