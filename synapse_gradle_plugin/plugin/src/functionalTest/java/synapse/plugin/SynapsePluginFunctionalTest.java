package synapse.plugin;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTimeoutPreemptively;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.util.Locale;
import org.gradle.testkit.runner.BuildResult;
import org.gradle.testkit.runner.GradleRunner;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class SynapsePluginFunctionalTest {
  @TempDir Path projectDir;

  @Test
  void deployRunsAfterRobotDeployWithCurrentInstallerArguments() throws IOException {
    Path log = projectDir.resolve("deploy.log");
    String python = stubSynapseProject(log, false);
    writeBuildScript(python, log, "");

    BuildResult result = run("deploy");

    assertTrue(result.getOutput().contains("Deploying Synapse project"));
    String calls = readLog(log);
    String deployArgs = "args=-m synapse_installer deploy --yes --no-logs ionic";
    assertTrue(calls.contains("robot-deploy"), calls);
    assertTrue(calls.contains(deployArgs), calls);
    assertTrue(calls.indexOf("robot-deploy") < calls.indexOf(deployArgs), calls);
    assertTrue(
        calls.lines().anyMatch(line -> line.startsWith("cwd=") && line.contains("synapseproject")),
        calls);
  }

  @Test
  void deployCanBeDisabled() throws IOException {
    Path log = projectDir.resolve("disabled.log");
    String python = stubSynapseProject(log, false);
    writeBuildScript(python, log, "enabled = false");

    BuildResult result = run("synapseDeploy");

    assertTrue(result.getOutput().contains("Synapse deployment is disabled."));
    assertFalse(Files.exists(log));
  }

  @Test
  void simulateJavaTaskGraphStartsSynapseBeforeRobotSimulation() throws IOException {
    Path log = projectDir.resolve("sim.log");
    String python = stubSynapseProject(log, false);
    writeBuildScript(python, log, "");

    String output = run("--dry-run", "simulateJava").getOutput();

    assertTrue(output.contains(":synapseSimStart"), output);
    assertTrue(output.contains(":simulateJava"), output);
    assertTrue(output.contains(":synapseSimStop"), output);
    assertTrue(output.indexOf(":synapseSimStart") < output.indexOf(":simulateJava"), output);
    assertTrue(output.indexOf(":simulateJava") < output.indexOf(":synapseSimStop"), output);
  }

  @Test
  void synapseSimLifecycleStartsRobotSimulation() throws IOException {
    Path log = projectDir.resolve("lifecycle.log");
    String python = stubSynapseProject(log, true);
    writeBuildScript(python, log, "");

    assertTimeoutPreemptively(Duration.ofMinutes(2), () -> run("synapseSim"));

    String calls = readLog(log);
    assertTrue(calls.contains("robot-sim"), calls);
    assertTrue(calls.contains("main.py"), calls);
  }

  private Path synapseProjectDir() {
    return projectDir.resolve("synapseproject");
  }

  private BuildResult run(String... tasks) {
    String[] arguments = new String[tasks.length + 1];
    arguments[0] = "--stacktrace";
    System.arraycopy(tasks, 0, arguments, 1, tasks.length);

    return GradleRunner.create()
        .withProjectDir(projectDir.toFile())
        .withArguments(arguments)
        .withPluginClasspath()
        .build();
  }

  /**
   * Creates a real Python project that behaves like Synapse. Using Python modules instead of a
   * platform-specific executable wrapper keeps the functional tests identical on Linux, macOS and
   * Windows.
   */
  private String stubSynapseProject(Path log, boolean blockInSimulation) throws IOException {
    Path dir = synapseProjectDir();
    Files.createDirectories(dir);
    Files.writeString(dir.resolve(".synapseproject"), "name: test\n");
    Files.writeString(dir.resolve("main.py"), pythonLogScript(log, blockInSimulation, "main.py "));

    Path installer = Files.createDirectories(dir.resolve("synapse_installer"));
    Files.writeString(installer.resolve("__init__.py"), "");
    Files.writeString(
        installer.resolve("__main__.py"), pythonLogScript(log, false, "-m synapse_installer "));

    return isWindows() ? "python" : "python3";
  }

  private void writeBuildScript(String python, Path log, String extraConfig) throws IOException {
    String build =
        "plugins {\n"
            + "    id 'java'\n"
            + "    id 'synapse.plugin'\n"
            + "}\n"
            + "\n"
            + "synapse {\n"
            + "    projectName = 'synapseproject'\n"
            + "    pythonExecutable = '"
            + groovyString(python)
            + "'\n"
            + "    deviceName = 'ionic'\n"
            + extraConfig
            + "\n"
            + "}\n"
            + "\n"
            + "tasks.register('deploy') {\n"
            + "    doLast {\n"
            + "        new File('"
            + groovyString(log)
            + "').append('robot-deploy\\n')\n"
            + "    }\n"
            + "}\n"
            + "\n"
            + "tasks.register('simulateJava') {\n"
            + "    doLast {\n"
            + "        new File('"
            + groovyString(log)
            + "').append('robot-sim\\n')\n"
            + "    }\n"
            + "}\n";
    Files.writeString(projectDir.resolve("build.gradle"), build, StandardCharsets.UTF_8);
    Files.writeString(projectDir.resolve("settings.gradle"), "rootProject.name = 'test-robot'\n");
  }

  private static String pythonLogScript(
      Path log, boolean blockInSimulation, String argumentPrefix) {
    String body =
        "import pathlib\n"
            + "import sys\n"
            + "import time\n"
            + "\n"
            + "log = pathlib.Path("
            + pythonString(log)
            + ")\n"
            + "with log.open('a', encoding='utf-8') as stream:\n"
            + "    stream.write('cwd=' + str(pathlib.Path.cwd()) + '\\n')\n"
            + "    stream.write('args="
            + argumentPrefix
            + "' + ' '.join(sys.argv[1:]) + '\\n')\n";
    if (blockInSimulation) {
      body += "\nif '--sim' in sys.argv:\n    while True:\n        time.sleep(0.05)\n";
    }
    return body;
  }

  private String readLog(Path log) throws IOException {
    return Files.readString(log, StandardCharsets.UTF_8);
  }

  private static boolean isWindows() {
    return System.getProperty("os.name", "").toLowerCase(Locale.ROOT).contains("win");
  }

  private static String groovyString(Path path) {
    return groovyString(path.toString());
  }

  private static String groovyString(String value) {
    return value.replace("\\", "/").replace("'", "\\'");
  }

  private static String pythonString(Path path) {
    return "\"" + path.toString().replace("\\", "\\\\").replace("\"", "\\\"") + "\"";
  }
}
