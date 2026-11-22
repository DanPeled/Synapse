package synapse.plugin;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTimeoutPreemptively;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.attribute.PosixFilePermissions;
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
    Path python = writePythonStub(log, false);
    writeSynapseProject();
    writeBuildScript(python, log, "");

    BuildResult result = run("deploy");

    assertTrue(result.getOutput().contains("Deploying Synapse project"));
    String calls = readLog(log);
    String deployArgs = "args=-m synapse_installer deploy --yes --no-logs ionic";
    assertTrue(calls.contains("robot-deploy"), calls);
    assertTrue(calls.contains(deployArgs), calls);
    assertTrue(calls.indexOf("robot-deploy") < calls.indexOf(deployArgs), calls);
    assertTrue(calls.contains("cwd=" + synapseProjectDir().toAbsolutePath()), calls);
  }

  @Test
  void deployCanBeDisabled() throws IOException {
    Path log = projectDir.resolve("disabled.log");
    Path python = writePythonStub(log, false);
    writeSynapseProject();
    writeBuildScript(python, log, "enabled = false");

    BuildResult result = run("synapseDeploy");

    assertTrue(result.getOutput().contains("Synapse deployment is disabled."));
    assertFalse(Files.exists(log));
  }

  @Test
  void simulateJavaStartsSynapseAndRobotSimulationTogether() throws IOException {
    Path log = projectDir.resolve("sim.log");
    Path python = writePythonStub(log, true);
    writeSynapseProject();
    writeBuildScript(python, log, "");

    assertTimeoutPreemptively(Duration.ofMinutes(2), () -> run("simulateJava"));

    String calls = readLog(log);
    String simArgs =
        "args=" + synapseProjectDir().resolve("main.py").toAbsolutePath() + " --sim --headless";
    assertTrue(calls.contains(simArgs), calls);
    assertTrue(calls.contains("robot-sim"), calls);
    assertTrue(calls.indexOf(simArgs) < calls.indexOf("robot-sim"), calls);
  }

  @Test
  void synapseSimLifecycleStartsRobotSimulation() throws IOException {
    Path log = projectDir.resolve("lifecycle.log");
    Path python = writePythonStub(log, true);
    writeSynapseProject();
    writeBuildScript(python, log, "");

    assertTimeoutPreemptively(Duration.ofMinutes(2), () -> run("synapseSim"));

    String calls = readLog(log);
    assertTrue(calls.contains("robot-sim"), calls);
    assertTrue(
        calls.contains("args=" + synapseProjectDir().resolve("main.py").toAbsolutePath()), calls);
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

  private void writeSynapseProject() throws IOException {
    Files.createDirectories(synapseProjectDir());
    Files.writeString(synapseProjectDir().resolve(".synapseproject"), "name: test\n");
    Files.writeString(
        synapseProjectDir().resolve("main.py"),
        "from synapse.core.synapse import Synapse\n" + "Synapse.createAndRunRuntime()\n");
  }

  private void writeBuildScript(Path python, Path log, String extraConfig) throws IOException {
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

  private Path writePythonStub(Path log, boolean blockInSimulation) throws IOException {
    String python = isWindows() ? "python" : "python3";
    Path script = projectDir.resolve("fake_synapse.py");
    String body =
        "import pathlib\n"
            + "import signal\n"
            + "import sys\n"
            + "import time\n"
            + "\n"
            + "log = pathlib.Path(\""
            + pythonString(log)
            + "\")\n"
            + "with log.open('a', encoding='utf-8') as stream:\n"
            + "    stream.write('cwd=' + str(pathlib.Path.cwd()) + '\\n')\n"
            + "    stream.write('args=' + ' '.join(sys.argv[1:]) + '\\n')\n";
    if (blockInSimulation) {
      body +=
          "\n"
              + "if '--sim' in sys.argv:\n"
              + "    def stop(*_):\n"
              + "        with log.open('a', encoding='utf-8') as stream:\n"
              + "            stream.write('sim-stopped\\n')\n"
              + "        raise SystemExit(0)\n"
              + "\n"
              + "    signal.signal(signal.SIGTERM, stop)\n"
              + "    while True:\n"
              + "        time.sleep(0.05)\n";
    }
    Files.writeString(script, body, StandardCharsets.UTF_8);

    if (isWindows()) {
      Path wrapper = projectDir.resolve("fake_python.bat");
      Files.writeString(
          wrapper,
          "@echo off\r\n\"" + python + "\" \"" + script.toString().replace('\\', '/') + "\" %*\r\n",
          StandardCharsets.UTF_8);
      return wrapper;
    }

    Path wrapper = projectDir.resolve("fake_python");
    Files.writeString(
        wrapper,
        "#!/bin/sh\nexec " + python + " " + shellQuote(script.toString()) + " \"$@\"\n",
        StandardCharsets.UTF_8);
    Files.setPosixFilePermissions(wrapper, PosixFilePermissions.fromString("rwxr-xr-x"));
    return wrapper;
  }

  private String readLog(Path log) throws IOException {
    return Files.readString(log, StandardCharsets.UTF_8);
  }

  private static boolean isWindows() {
    return System.getProperty("os.name", "").toLowerCase(Locale.ROOT).contains("win");
  }

  private static String groovyString(Path path) {
    return path.toString().replace("\\", "/").replace("'", "\\'");
  }

  private static String pythonString(Path path) {
    return path.toString().replace("\\", "\\\\").replace("\"", "\\\"");
  }

  private static String shellQuote(String value) {
    return "'" + value.replace("'", "'\\''") + "'";
  }
}
