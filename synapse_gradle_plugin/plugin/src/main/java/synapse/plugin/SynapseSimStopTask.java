package synapse.plugin;

import javax.inject.Inject;
import org.gradle.api.DefaultTask;
import org.gradle.api.tasks.TaskAction;

/** Stops the Synapse simulator started by {@link SynapseSimStartTask}. */
public abstract class SynapseSimStopTask extends DefaultTask {
  private final SynapseExtension synapse;

  @Inject
  public SynapseSimStopTask(SynapseExtension synapse) {
    this.synapse = synapse;
  }

  @TaskAction
  public void stop() {
    synapse.stopSim(getLogger());
  }
}
