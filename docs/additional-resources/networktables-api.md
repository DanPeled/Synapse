---
icon: server
---

# NetworkTables API

Synapse publishes everything over NetworkTables. SynapseLib wraps this API, but you can also read the tables directly from a dashboard, a logging tool, or your own code.

{% hint style="warning" %}
The raw API is stable enough for reading, but some values are binary. Use [SynapseLib](../robot-interfacing/synapse-bridge/README.md) for typed results, automatic MessagePack decoding, and type-safe settings.
{% endhint %}

## Table layout

Everything lives under the root table configured on the **Settings** page. The default is `Synapse`.

```text
Synapse/
├── version              string
├── web_ui               string
├── metrics              double[]
└── <camera-name>/
    ├── pipeline         int
    ├── pipeline_type    string
    ├── record           bool
    ├── view_id          string
    ├── captureLatency   double
    ├── processLatency   double
    ├── data/
    │   ├── results      raw (MessagePack)
    │   └── <key>        any supported value
    └── settings/
        ├── <key>        setting value
        └── ...
```

`<camera-name>` is the camera nickname from the dashboard. Renaming a camera changes this subtable.

## Root keys

| Key | Type | Description |
| --- | --- | --- |
| `version` | `string` | Synapse runtime version |
| `web_ui` | `string` | Dashboard address as `<ip>:3000` |
| `metrics` | `double[]` | Hardware metrics, updated periodically |

### Metrics array

| Index | Metric | Unit |
| --- | --- | --- |
| `0` | CPU temperature | °C |
| `1` | CPU usage | % |
| `2` | Total memory | MB |
| `3` | Uptime | seconds |
| `4` | GPU memory split | MB (`0` when unavailable) |
| `5` | Used RAM | MB |
| `6` | Used disk | % |
| `7` | NPU usage | % (`0` when unavailable) |

Unsupported metrics report `0`, `-1`, or `0.0` depending on the platform. See the [Settings Page](../usage/built-in-pipelines-1/settings-page.md) for the same values in the dashboard.

## Camera keys

| Key | Type | Description |
| --- | --- | --- |
| `pipeline` | `int` | Active pipeline index. Write to switch pipelines. |
| `pipeline_type` | `string` | Pipeline type name, such as `ApriltagPipeline` or `MyPipeline` |
| `record` | `bool` | Recording state. Write to start or stop recording. |
| `view_id` | `string` | Dashboard view selector |
| `captureLatency` | `double` | Capture latency in seconds. Currently always `0.0`. |
| `processLatency` | `double` | Pipeline processing time in seconds |
| `data/results` | `raw` | MessagePack-encoded final pipeline result |
| `data/<key>` | Any | Auxiliary value published with `setDataValue` |
| `settings/<key>` | Any | Setting value, only when settings publishing is enabled |

Each camera subtable is created from the camera nickname. For example, a camera named `camera0` publishes under `Synapse/camera0`.

## Reading values

{% tabs %}
{% tab title="Java" %}
```java
import edu.wpi.first.networktables.NetworkTableInstance;

var root = NetworkTableInstance.getDefault().getTable("Synapse");
var camera = root.getSubTable("camera0");

long pipeline = camera.getEntry("pipeline").getInteger(-1);
String type = camera.getEntry("pipeline_type").getString("unknown");
double latency = camera.getEntry("processLatency").getDouble(0.0);
boolean recording = camera.getEntry("record").getBoolean(false);

boolean hasResults = camera
    .getSubTable("data")
    .getEntry("hasResults")
    .getBoolean(false);
```
{% endtab %}

{% tab title="Python" %}
```python
from ntcore import NetworkTableInstance

root = NetworkTableInstance.getDefault().getTable("Synapse")
camera = root.getSubTable("camera0")

pipeline = camera.getEntry("pipeline").getInteger(-1)
pipeline_type = camera.getEntry("pipeline_type").getString("unknown")
latency = camera.getEntry("processLatency").getDouble(0.0)
recording = camera.getEntry("record").getBoolean(False)

has_results = (
    camera.getSubTable("data")
    .getEntry("hasResults")
    .getBoolean(False)
)
```
{% endtab %}
{% endtabs %}

Always pass a default. Before the runtime publishes a key, the entry exists but has no value of that type.

## Reading final results

`data/results` is a `raw` entry containing MessagePack bytes. Decode it with the result class:

{% tabs %}
{% tab title="Java" %}
```java
import com.fasterxml.jackson.core.type.TypeReference;
import synapse.pipelines.apriltag.ApriltagResult;

byte[] raw = camera
    .getSubTable("data")
    .getEntry("results")
    .getRaw(new byte[0]);

if (raw.length > 0) {
  ApriltagResult result = new com.fasterxml.jackson.databind.ObjectMapper(
          new org.msgpack.jackson.dataformat.MessagePackFactory())
      .readValue(raw, new TypeReference<ApriltagResult>() {});
}
```

In practice, use `camera.getResults(SynapsePipelineType.kApriltag)` or [SynapseLib](../robot-interfacing/synapse-bridge/getting-target-data.md) rather than decoding by hand.
{% endtab %}

{% tab title="Python" %}
```python
import msgpack

raw = camera.getSubTable("data").getEntry("results").getRaw(b"")
if raw:
    result = msgpack.loads(raw, raw=False)
```
{% endtab %}
{% endtabs %}

## Writing values

NetworkTables writes are picked up by the runtime:

| Key | Effect |
| --- | --- |
| `<camera>/pipeline` | Switch the active pipeline |
| `<camera>/record` | Start or stop recording |
| `<camera>/settings/<key>` | Change a setting, when settings publishing is enabled |

Settings writes are validated by the runtime. Invalid values are rejected. Changes are applied immediately but are only saved to disk when you press **Save** in the dashboard.

{% hint style="warning" %}
The dashboard and NetworkTables can both change settings. If you write settings from robot code every loop, you will fight the dashboard and any other writer. Write only when the value actually needs to change.
{% endhint %}

## When to use SynapseLib instead

| Task | Raw NetworkTables | SynapseLib |
| --- | --- | --- |
| Read a quick flag | Fine | Fine |
| Decode AprilTag results | Error-prone | `getResults(...)` |
| Read latency | Fine | `getProcessLatency()` |
| Change a pipeline | Fine | `setPipeline(...)` |
| Type-safe settings | Manual typing | `getSetting(Setting<T>)` |
| Recording control | Fine | `setRecordStatus(...)` |

## Next steps

- [SynapseLib](../robot-interfacing/synapse-bridge/README.md)
- [Custom Pipeline Data](../robot-interfacing/synapse-bridge/custom-pipeline-data.md)
- [Sending Results](../usage/custom-pipelines/sending-results.md)
- [Known Issues](known-issues.md)
