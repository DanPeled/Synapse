package synapse.plugin;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.gradle.api.Project;
import org.gradle.testfixtures.ProjectBuilder;
import org.junit.jupiter.api.Test;

class SynapsePluginTest {
  @Test
  void registersDeployAndSimulationTasks() {
    Project project = ProjectBuilder.builder().build();
    project.getPluginManager().apply(SynapsePlugin.class);

    assertNotNull(project.getTasks().findByName("synapseDeploy"));
    assertNotNull(project.getTasks().findByName("synapseSim"));
    assertNotNull(project.getTasks().findByName("synapseSimStart"));
    assertNotNull(project.getTasks().findByName("synapseSimStop"));
  }

  @Test
  void extensionDefaultsMatchTheCurrentRuntime() {
    Project project = ProjectBuilder.builder().build();
    project.getPluginManager().apply(SynapsePlugin.class);
    SynapseExtension extension = project.getExtensions().getByType(SynapseExtension.class);

    assertEquals("synapseproject", extension.getProjectName());
    assertEquals("main.py", extension.getMainScript());
    assertTrue(extension.buildDeployArguments().contains("deploy"));
    assertTrue(extension.isHeadless());
    assertTrue(extension.buildSimArguments().contains("--sim"));
    assertTrue(extension.buildDeployArguments().contains("synapse_installer"));
  }
}
