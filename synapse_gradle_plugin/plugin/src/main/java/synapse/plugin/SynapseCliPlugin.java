package synapse.plugin;

import org.gradle.api.Plugin;
import org.gradle.api.Project;

public class SynapseCliPlugin implements Plugin<Project> {
  @Override
  public void apply(Project project) {
    StartupSettingsExtension ext =
        project.getExtensions().create("synapse", StartupSettingsExtension.class);

    var deploy =
        project
            .getTasks()
            .register(
                "synapseDeploy",
                DeployTask.class,
                task -> {
                  task.doFirst(
                      t -> {
                        if (ext.getProjectName() == null) {
                          throw new IllegalArgumentException("synapse.projectName must be set");
                        }
                        assert ext.getDeviceName() != null;

                        task.commandLine("python", "-m", "synapse_installer", "deploy");
                        task.args(ext.getDeviceName());
                      });
                });
  }
}
