# Synapse Gradle Plugin

[![Release](https://jitpack.io/v/DanPeled/Synapse.svg)](https://jitpack.io/#DanPeled/Synapse)

Wires a Synapse coprocessor project into a GradleRIO robot project.

The plugin uses the current `synapse_installer` CLI and the current simulated
camera runtime (`python main.py --sim`). It targets the Java 25 / Gradle 9.2
toolchain used by the 2027 robot projects in this repository.

## Apply the plugin

The published plugin is available from JitPack. Add the repository to your
robot project's `settings.gradle`:

```groovy
pluginManagement {
    repositories {
        gradlePluginPortal()
        maven { url "https://jitpack.io" }
    }
}
```

Then apply it in the robot project's `build.gradle` using the plugin tag:

```groovy
plugins {
    id "org.wpilib.GradleRIO"
    id "synapse.plugin" version "synapse-gradle-plugin-2027.0.0a1"
}
```

To use the plugin directly from a Synapse checkout, add the included build to
`settings.gradle` instead:

```groovy
pluginManagement {
    resolutionStrategy {
        eachPlugin {
            if (requested.id.id == "synapse.plugin") {
                useVersion("2027.0.0a1")
            }
        }
    }
    includeBuild("../synapse_gradle_plugin")
}
```

and apply it without a version:

```groovy
plugins {
    id "org.wpilib.GradleRIO"
    id "synapse.plugin"
}

synapse {
    projectName = "synapseproject" // directory containing .synapseproject
    deviceName = "ionic"           // omit or use devices = [...] for all devices
    installDependencies = false    // set true to sync dependencies before deploying
}
```

### Configuration

| Property | Default | Purpose |
| --- | --- | --- |
| `projectName` | `synapseproject` | Synapse project directory, relative to the robot project or its root |
| `projectDir` | — | Explicit path to the Synapse project; overrides `projectName` |
| `mainScript` | `main.py` | Runtime entry point used in simulation |
| `pythonExecutable` | `python3` (`python` on Windows) | Python interpreter with `synapsefrc` installed |
| `deviceName` | — | Single deploy target; omit to deploy to all configured devices |
| `devices` | `[]` | Additional deploy targets |
| `installDependencies` | `false` | Use `synapse_installer deploy`; set `true` to sync dependencies first with `install` |
| `followLogs` | `false` | Follow runtime logs after deployment |
| `dryRun` | `false` | Pass `--dry-run` to the installer |
| `enabled` | `true` | Disable all Synapse tasks |
| `simEnabled` | `true` | Disable simulation integration only |
| `headless` | `true` | Pass `--headless` to the simulated runtime |

## Tasks and lifecycle

- `synapseDeploy` deploys the Synapse project. It is a finalizer of GradleRIO's
  `deploy`, so `./gradlew deploy` deploys robot code and coprocessor code together.
- `synapseSimStart` starts `python main.py --sim --headless` in the background.
- `synapseSimStop` stops that process and its children.
- `simulateJava` depends on `synapseSimStart` and is finalized by
  `synapseSimStop`, so robot simulation and Synapse simulation start and stop
  together.
- `synapseSim` is a convenience lifecycle task that runs `simulateJava` with
  Synapse simulation enabled.

The simulator connects to NetworkTables on `127.0.0.1`, which is where WPILib
robot simulation publishes its server. A JVM shutdown hook stops the simulator
if Gradle is interrupted.

## Building and publishing this plugin

```sh
cd synapse_gradle_plugin
./gradlew build
```

The build runs unit tests and Gradle TestKit functional tests that exercise the
deploy and simulation lifecycles with a stub Python project. To publish all
plugin publications to your local Maven repository, run:

```sh
./gradlew publishToMavenLocal
```

JitPack uses the root `jitpack.yml` to build with JDK 25 and publish both the
`synapse.plugin` plugin marker and the implementation artifact. Request the
tagged version (`synapse-gradle-plugin-<synapseVersion>`) on
[JitPack](https://jitpack.io/#DanPeled/Synapse) to trigger a publication.
