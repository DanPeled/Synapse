package synapse.plugin;

import org.gradle.api.Plugin;
import org.gradle.api.Project;
import org.gradle.api.Task;
import org.gradle.api.tasks.TaskProvider;

/** Wires Synapse deployment and simulation into a GradleRIO robot project. */
public class SynapsePlugin implements Plugin<Project> {
  @Override
  public void apply(Project project) {
    SynapseExtension synapse =
        project.getExtensions().create("synapse", SynapseExtension.class, project);

    TaskProvider<SynapseDeployTask> deploy =
        project.getTasks().register("synapseDeploy", SynapseDeployTask.class, synapse);
    deploy.configure(task -> {
      task.setGroup("synapse");
      task.setDescription("Deploy the Synapse coprocessor project with the robot code.");
      task.getOutputs().upToDateWhen(ignored -> false);
    });

    TaskProvider<SynapseSimStartTask> simStart =
        project.getTasks().register("synapseSimStart", SynapseSimStartTask.class, synapse);
    simStart.configure(task -> {
      task.setGroup("synapse");
      task.setDescription("Start the Synapse simulator before robot simulation.");
      task.getOutputs().upToDateWhen(ignored -> false);
    });

    TaskProvider<SynapseSimStopTask> simStop =
        project.getTasks().register("synapseSimStop", SynapseSimStopTask.class, synapse);
    simStop.configure(task -> {
      task.setGroup("synapse");
      task.setDescription("Stop the Synapse simulator after robot simulation.");
      task.getOutputs().upToDateWhen(ignored -> false);
    });

    TaskProvider<Task> simLifecycle =
        project
            .getTasks()
            .register(
                "synapseSim",
                task -> {
                  task.setGroup("synapse");
                  task.setDescription("Run robot simulation with the Synapse simulator.");
                  task.dependsOn(simStart);
                  task.finalizedBy(simStop);
                });

    project
        .getTasks()
        .matching(task -> task.getName().equals("deploy"))
        .configureEach(task -> task.finalizedBy(deploy));

    project
        .getTasks()
        .matching(task -> task.getName().equals("simulateJava"))
        .configureEach(task -> {
          task.dependsOn(simStart);
          task.finalizedBy(simStop);
        });

    // GradleRIO registers simulateJava while the robot build script is evaluated.
    // Resolve it afterwards so `synapseSim` runs the complete robot simulation.
    project.afterEvaluate(evaluated -> {
      Task robotSimulation = evaluated.getTasks().findByName("simulateJava");
      if (robotSimulation != null) {
        simLifecycle.configure(task -> task.dependsOn(robotSimulation));
      }
    });
  }
}
