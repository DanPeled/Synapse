---
description: Run a Synapse project on your laptop, with or without simulated cameras.
icon: robot
---

# Working Without a Robot

You can develop and test a Synapse project before you have a robot or a coprocessor. There are two modes:

| Mode | Command | Cameras | NetworkTables server |
| --- | --- | --- | --- |
| **Server mode** | `python main.py --server` | Real cameras on your computer | Started by Synapse on `127.0.0.1` |
| **Simulation mode** | `python main.py --sim` | Simulated 3D field cameras | An existing local server, or started by Synapse with `--server` |

Both modes run the same runtime, UI, pipelines, and NetworkTables code. Only the camera source and the NetworkTables server differ.

{% hint style="info" %}
Run these commands from the root of a Synapse project, with the same Python environment where `synapsefrc` is installed.
{% endhint %}

## Server mode

Server mode makes the runtime host its own NetworkTables server:

```bash
python main.py --server
```

- The runtime starts a NetworkTables server on `127.0.0.1`.
- It also connects a client to that server.
- Real cameras attached to your computer are used.
- The dashboard is available at `http://localhost:3000`.

Use server mode when you want to test pipelines with a USB camera plugged into your laptop, or when you want robot code or a dashboard on the same computer to read Synapse data.

{% hint style="warning" %}
Server mode uses the cameras on the computer running the command. It does not replace a missing camera with a simulated one.
{% endhint %}

## Simulation mode

Simulation mode replaces the camera implementation with `SimCamera`. Each configured camera renders a 3D view of the FRC field, including AprilTags, from a simulated robot pose.

```bash
python main.py --sim
```

When used alone, `--sim` connects to a NetworkTables server already running at `127.0.0.1`. This is the mode to use with the [WPILib robot simulation](https://docs.wpilib.org/en/stable/docs/software/wpilib-tools/robot-simulation/introduction.html): WPILib starts the server, and Synapse connects as a client.

To run simulation without WPILib, start a server too:

```bash
python main.py --sim --server
```

This runs the simulation standalone, which is the easiest way to try the UI and pipelines with no robot, no coprocessor, and no camera.

Simulation requires Chrome or Chromium. See [Simulation](simulation.md) for the full setup, NetworkTables controls, and defaults.

## Headless mode

```bash
python main.py --headless
```

`--headless` skips the terminal status display. It does **not** disable the web UI, the camera streams, or the pipelines. You can combine it with the other flags:

```bash
python main.py --sim --server --headless
```

## Which mode should I use?

| Goal | Mode |
| --- | --- |
| Test a USB camera on my laptop | `--server` |
| Test with WPILib robot simulation | `--sim` |
| Try Synapse with no hardware at all | `--sim --server` |
| Run on a coprocessor on a robot | no flags |
| Run on a coprocessor as a standalone NetworkTables server | `--server` |

## Viewing the dashboard

In every mode, open:

```text
http://localhost:3000
```

The runtime publishes its dashboard address to NetworkTables under `web_ui`.

## Next steps

- [Simulation](simulation.md)
- [Quick Start](../getting-started/quick-start/README.md)
- [UI Interaction](built-in-pipelines-1/README.md)
- [Networking](../getting-started/quick-start/networking.md)
