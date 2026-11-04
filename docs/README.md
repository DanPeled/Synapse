---
icon: house
layout:
  width: default
  title:
    visible: true
  description:
    visible: true
  tableOfContents:
    visible: true
  outline: false
  pagination:
    visible: true
  metadata:
    visible: true
---

# Home

<figure><img src=".gitbook/assets/SynapseHeader.png" alt=""><figcaption></figcaption></figure>

Synapse is a vision processing library and toolset for [FRC](https://www.firstinspires.org/robotics/frc). It lets you run computer vision on a small Linux computer (a **coprocessor**) attached to your robot, then use the results in your robot code.

If you have never used Synapse before, start with [How Synapse Works](getting-started/how-synapse-works.md) and then follow the [Quick Start](getting-started/quick-start/README.md).

## What you get

<table data-view="cards"><thead><tr><th></th><th></th><th data-hidden data-card-cover data-type="files"></th></tr></thead><tbody><tr><td><strong>Extendable</strong></td><td>Use the built-in AprilTag and color pipelines, or write your own Python pipeline</td><td><a href=".gitbook/assets/settings.png">settings.png</a></td></tr><tr><td><strong>Fast to iterate</strong></td><td>Deploy your vision project to the coprocessor like robot code, with one command</td><td><a href=".gitbook/assets/rush.png">rush.png</a></td></tr><tr><td><strong>Built-in UI</strong></td><td>Tune settings, watch camera streams, and inspect results live from a web browser</td><td><a href=".gitbook/assets/ux-design.png">ux-design.png</a></td></tr></tbody></table>

## The pieces of Synapse

| Piece | What it does | Runs on |
| --- | --- | --- |
| **Synapse runtime** (`synapsefrc`) | Reads cameras, runs pipelines, and publishes results | Coprocessor |
| **Web UI** | Live camera feeds, pipeline management, settings, logs, and device controls | Any browser on the same network |
| **SynapseLib** | A Java/Python library that reads results and changes settings from robot code | RoboRIO |
| **Synapse Manager** | A desktop app that finds devices, opens their dashboards, and deploys projects | Your development computer |
| **Synapse Sim** | Simulated cameras that render a 3D field, so you can test without hardware | Your development computer |

## Choose your path

{% tabs %}
{% tab title="I'm new to Synapse" %}
1. Read [How Synapse Works](getting-started/how-synapse-works.md).
2. Check [Common Hardware Setups](getting-started/quick-start/common-hardware-setups.md) and [Selecting Hardware](getting-started/hardware-selection/selecting-hardware.md).
3. Install the software and create your first project in [Quick Start](getting-started/quick-start/README.md).
4. Connect your robot code with [SynapseLib](robot-interfacing/synapse-bridge/README.md).
{% endtab %}

{% tab title="I have a coprocessor" %}
1. Install the runtime in [Installing Software](getting-started/installing-software.md).
2. Create and deploy a project with [Project Management](usage/project-management/README.md).
3. Open `http://<device-ip>:3000` and tune your pipeline in [UI Interaction](usage/built-in-pipelines-1/README.md).
{% endtab %}

{% tab title="I want to write a pipeline" %}
1. Learn the pipeline lifecycle in [How Synapse Works](getting-started/how-synapse-works.md).
2. Follow [Custom Pipelines](usage/custom-pipelines/README.md).
3. Add tunable settings with the [Settings API](usage/custom-pipelines/settings-api.md).
4. Publish data with [Sending Results](usage/custom-pipelines/sending-results.md).
{% endtab %}

{% tab title="I have no robot yet" %}
1. Try [Working without a robot](usage/working-without-a-robot.md).
2. Run the 3D field renderer with [Simulation](usage/simulation.md).
3. Test AprilTags and robot pose estimates before touching hardware.
{% endtab %}
{% endtabs %}

## Requirements at a glance

- A Linux coprocessor (Orange Pi 5, Raspberry Pi 5, or similar) with SSH enabled.
- Python 3.11–3.14 on the coprocessor. The installer can build Python 3.12 automatically if none is available.
- A development computer with Python 3.11–3.14.
- A camera supported by OpenCV/V4L2, or the built-in simulation cameras.
- Internet access on the coprocessor for the first install, so Python packages can be downloaded.

## Source Code

The source code for Synapse is available on [GitHub](https://github.com/DanPeled/Synapse).

## Contact Us

To report a bug or request a feature, [open an issue on GitHub](https://github.com/DanPeled/Synapse) or join the [Discord server](https://discord.gg/zHJRV8Stj3).

[^1]: FIRST Robotics Competition
