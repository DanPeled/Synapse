---
description: Read camera results and control pipelines from Java or Python robot code.
icon: plug
---

# SynapseLib: Robot Code Interface

SynapseLib is the library your robot code uses to talk to Synapse. It hides the raw NetworkTables layout behind typed classes, so you work with objects such as `SynapseCamera` and `ApriltagResult` instead of byte arrays and topic names.

With SynapseLib you can:

- Read the latest pipeline results.
- Check which pipeline is running.
- Read recording status and latency.
- Change the active pipeline.
- Read camera settings (when settings publishing is enabled).
- Convert a camera pose to a robot pose (Java).

{% hint style="warning" %}
Synapse and SynapseLib communicate over NetworkTables. Make sure the runtime is connected to the same NetworkTables server as your robot code. On a robot, that server runs on the robot controller (SystemCore in the 2027 examples). See [Networking](../../getting-started/quick-start/networking.md).
{% endhint %}

## How it fits together

```mermaid
flowchart LR
    A[Camera] --> B[Synapse runtime]
    B -->|NetworkTables| C[SynapseLib]
    C --> D[Robot code]
    B -->|WebSocket| E[Dashboard]
```

The runtime publishes one NetworkTables subtable per camera under the root table (default `Synapse`):

```text
Synapse/<camera-name>/
```

SynapseLib wraps that subtable. The camera name must match the name configured in the dashboard.

## Supported languages

| Language | Package | Status |
| --- | --- | --- |
| Java | `synapse` vendordep | Available for the 2027 alpha |
| Python | `synapsefrclib` (`synapselib`) | Available for the 2027 alpha |

{% hint style="warning" %}
The 2027 alpha uses WPILib 2027 alpha 8, Java 25, and Gradle 9.2.0. Replace `WPILibNewCommands.json` with `CommandsV2.json` in robot projects. The Python package is `2027.0.0a1`; the pinned 2027 Java vendordep is not published yet, so use the `dev` vendordep.
{% endhint %}

## Pages

- [Installing SynapseLib](installing-synapse-bridge.md)
- [Getting Target Data](getting-target-data.md)
- [Robot Pose](robot-pose.md)
- [Runtime Camera Settings](runtime-camera-settings.md)
- [Custom Pipeline Data](custom-pipeline-data.md)

## A minimal example

{% tabs %}
{% tab title="Java" %}
```java
import synapse.SynapseCamera;

SynapseCamera camera = new SynapseCamera("camera0", "Synapse");
```
{% endtab %}

{% tab title="Python" %}
```python
from synapselib import SynapseCamera

camera = SynapseCamera("camera0", "Synapse")
```
{% endtab %}
{% endtabs %}

## Next steps

- [Installing SynapseLib](installing-synapse-bridge.md)
- [Getting Target Data](getting-target-data.md)
- [NetworkTables API](../../additional-resources/networktables-api.md)
