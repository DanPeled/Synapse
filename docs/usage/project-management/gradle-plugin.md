---
description: Deploy a Synapse project from your GradleRIO robot project and start simulation with robot code.
icon: plug
---

# Gradle Plugin

The Synapse Gradle plugin is optional. It connects your robot code project to your Synapse project so you can:

- deploy robot code and coprocessor code with one Gradle command;
- start Synapse simulation when you run WPILib robot simulation;
- stop the simulator when you stop Gradle, including with `Ctrl+C`.

This plugin is for the 2027 alpha toolchain: Java 25, Gradle 9.2, and GradleRIO 2027.

## Before you start

You need:

- a GradleRIO robot project;
- a Synapse project created with [Project Management](README.md), including its `.synapseproject` file;
- Python with `synapsefrc` installed on your development computer;
- network access to the coprocessor when deploying.

The plugin calls the same installer commands described in [Deploy Commands](README.md#deploy-commands). It does not replace those commands.

## Add the plugin

JitPack publishes the Gradle plugin as a module under the repository group. Because of that, you must map the plugin ID to the published module in `settings.gradle`:

```groovy
pluginManagement {
    repositories {
        gradlePluginPortal()
        maven { url "https://jitpack.io" }
    }
    resolutionStrategy {
        eachPlugin {
            if (requested.id.id == "synapse.plugin") {
                useModule("com.github.DanPeled.Synapse:plugin:synapse-gradle-plugin-2027.0.0a1")
            }
        }
    }
}
```

{% hint style="info" %}
The `useModule(...)` line is required. Without it, Gradle looks for the plugin under the wrong name and cannot find it on JitPack.
{% endhint %}

Then apply the plugin in your robot project's `build.gradle`:

```groovy
plugins {
    id "org.wpilib.GradleRIO"
    id "synapse.plugin"
}
```

If you are working from a Synapse source checkout instead of JitPack, see the [plugin README](https://github.com/DanPeled/Synapse/blob/main/synapse_gradle_plugin/README.md) for the `includeBuild` setup.

## Configure the plugin

Add a `synapse` block to `build.gradle`:

```groovy
synapse {
    projectName = "synapseproject" // folder containing .synapseproject
    deviceName = "ionic"           // optional: one deploy target
    pythonExecutable = "python3"   // Python with synapsefrc installed
    installDependencies = false    // true syncs dependencies before deploy
}
```

| Setting | Default | What it does |
| --- | --- | --- |
| `projectName` | `synapseproject` | Synapse project folder, relative to the robot project |
| `projectDir` | none | Exact path to the Synapse project. Use this instead of `projectName` when the folder is elsewhere |
| `mainScript` | `main.py` | Project entry point used by simulation |
| `pythonExecutable` | `python3` | Python interpreter used for deploy and simulation. On Windows the default is `python` |
| `deviceName` | none | Deploy to one named device. Omit it to deploy to every configured device |
| `devices` | empty | Extra device names to deploy to |
| `installDependencies` | `false` | Use `install` (sync, then deploy) instead of `deploy`. Set this to `true` when you add Python dependencies |
| `followLogs` | `false` | Follow runtime logs after deploy |
| `dryRun` | `false` | Show what would be deployed without changing the device |
| `enabled` | `true` | Set to `false` to disable all Synapse tasks |
| `simEnabled` | `true` | Set to `false` to disable simulation integration only |
| `headless` | `true` | Pass `--headless` to the simulated runtime |

{% hint style="warning" %}
The `.synapseproject` file stores SSH passwords. Do not commit it to a public robot repository.
{% endhint %}

## Deploy robot and coprocessor code

```bash
./gradlew deploy
```

This runs the normal GradleRIO deploy, then runs `synapseDeploy` as a final step. Your robot code and Synapse project are both deployed.

To deploy only the Synapse project:

```bash
./gradlew synapseDeploy
```

Use `dryRun = true` to check the selected devices before a real deploy:

```bash
./gradlew synapseDeploy
```

The command prints the targets and exits without packaging or uploading anything.

## Simulate robot and vision together

```bash
./gradlew simulateJava
```

The plugin starts `python main.py --sim --headless` before robot simulation and stops it afterwards. You can also run:

```bash
./gradlew synapseSim
```

`synapseSim` is a shortcut that runs `simulateJava` with Synapse simulation enabled.

The simulated runtime connects to the local NetworkTables server at `127.0.0.1`, which is where WPILib robot simulation publishes. You do not need the `--server` flag. See [Simulation](../simulation.md) for field poses and simulation settings.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Gradle cannot find `synapse.plugin` | Confirm the `useModule(...)` mapping and the JitPack repository in `settings.gradle` |
| Deploy reaches the wrong device | Check `deviceName` and `devices`, or run `python -m synapse_installer device list` in the Synapse project |
| Python cannot import Synapse | Set `pythonExecutable` to the interpreter where you installed `synapsefrc` |
| New Python dependency is missing on the coprocessor | Set `installDependencies = true` once, or run `python -m synapse_installer install` from the Synapse project |
| Simulator does not see robot data | Make sure WPILib simulation is hosting NetworkTables at `127.0.0.1`, and that `simEnabled` is not `false` |

## Next steps

- [Deploy Commands](README.md#deploy-commands)
- [Simulation](../simulation.md)
- [Installing SynapseLib](../../robot-interfacing/synapse-bridge/installing-synapse-bridge.md)
