---
description: Publish pipeline results and auxiliary values to the dashboard and robot code.
icon: binary-circle-check
---

# Sending Results

Synapse gives every pipeline two ways to publish data:

| Kind | Method | Encoding | Read by |
| --- | --- | --- | --- |
| **Final results** | `self.setResults(result)` | MessagePack bytes | `SynapseCamera.getResults(...)` |
| **Auxiliary values** | `self.setDataValue(key, value)` | Native NetworkTables value | `data/<key>` entry |

Final results are the structured output of your pipeline. Auxiliary values are small extras such as a detection count, a flag, or a debug number.

{% hint style="info" %}
This page covers **sending** results. To read them in robot code, see [Custom Pipeline Data](../../robot-interfacing/synapse-bridge/custom-pipeline-data.md).
{% endhint %}

## Final results

### Define a result class

A result class must extend `PipelineResult`, or be decorated with `@pipelineResult`, which creates a dataclass and adds `PipelineResult` automatically.

```python
from synapse.core.pipeline import pipelineResult


@pipelineResult
class MyPipelineResult:
    count: int
    label: str
    confidence: float
```

The decorator is equivalent to:

```python
from dataclasses import dataclass
from synapse.core.results_api import PipelineResult


@dataclass
class MyPipelineResult(PipelineResult):
    count: int
    label: str
    confidence: float
```

{% hint style="warning" %}
Use `from synapse.core.results_api import PipelineResult` when you import it directly. `PipelineResult` is not exported from the top-level `synapse` package.
{% endhint %}

### Publish the result

Call `setResults` after each frame:

```python
class MyPipeline(Pipeline):
    def processFrame(self, img, timestamp):
        result = MyPipelineResult(count=3, label="fuel", confidence=0.92)
        self.setResults(result)
        return img
```

`setResults` writes to the `data/results` entry on the camera's NetworkTables table:

```text
<networktable>/<camera>/data/results
```

To clear the result, pass `None`:

```python
self.setResults(None)
```

### How values are serialized

`setResults` converts the result to plain Python values and then encodes it with MessagePack. The conversion rules are:

| Python value | Becomes |
| --- | --- |
| `int`, `float`, `str`, `bool`, `None` | The same value |
| `list`, `tuple`, `set` | A list |
| `dict` | A dict |
| `wpimath` geometry types | A list of numbers (see below) |
| Dataclass | A dict of field names to converted values |
| Other objects | A dict of public non-callable attributes |

Supported WPILib geometry types and their wire formats:

| Type | Wire format |
| --- | --- |
| `Translation2d` | `[x, y]` |
| `Translation3d` | `[x, y, z]` |
| `Rotation2d` | `degrees` |
| `Rotation3d` | `[roll, pitch, yaw]` in degrees |
| `Pose2d` | `[x, y, yaw]` (yaw in degrees) |
| `Pose3d` | `[x, y, z, roll, pitch, yaw]` (degrees) |
| `Transform2d` | `[x, y, yaw]` |
| `Transform3d` | `[x, y, z, roll, pitch, yaw]` |
| `Twist2d` | `[dx, dy, dtheta]` |
| `Twist3d` | `[dx, dy, dz, rx, ry, rz]` |

Field names are preserved exactly. If robot code uses a different field name, the value will not deserialize. For Java, use `@JsonProperty("field_name")` when the Java field name differs from the Python field name.

### Example: nested result

```python
from dataclasses import dataclass
from synapse.core.results_api import PipelineResult


@dataclass
class Target:
    id: int
    x: float
    y: float


@dataclass
class TargetResult(PipelineResult):
    targets: list[Target]
    best_id: int
```

This serializes to:

```json
{
  "targets": [
    {"id": 1, "x": 120.5, "y": 80.0}
  ],
  "best_id": 1
}
```

## Auxiliary values

Use `setDataValue` for small, directly readable values:

```python
self.setDataValue("hasResults", True)
self.setDataValue("tagCount", len(tags))
self.setDataValue("bestTagId", 7)
self.setDataValue("score", 0.87)
self.setDataValue("labels", ["left", "right"])
```

Each value is published to its own entry:

```text
<networktable>/<camera>/data/<key>
```

The dashboard shows auxiliary values in a table below the camera stream.

### Supported auxiliary types

| Type | NetworkTables type |
| --- | --- |
| `bool` | `boolean` |
| `int` | `int` |
| `float` | `double` |
| `str` | `string` |
| `bytes` | `raw` |
| `list` / `tuple` of `bool` | `boolean[]` |
| `list` / `tuple` of `int` | `int[]` |
| `list` / `tuple` of `float` | `double[]` |
| `list` / `tuple` of `str` | `string[]` |

{% hint style="warning" %}
A list must contain one type only. Mixed lists, dicts, and nested lists are not supported as auxiliary values. Use `setResults` for structured data.
{% endhint %}

### When to use which

| Need | Use |
| --- | --- |
| Robot code needs the full detection list | `setResults` |
| A dashboard operator wants a quick number | `setDataValue` |
| Values must be human-readable in NetworkTables | `setDataValue` |
| You need WPILib poses or nested objects | `setResults` |
| You need a flag such as `hasResults` | `setDataValue` |

The AprilTag pipeline uses both: it publishes the full `ApriltagResult` with `setResults` and flags such as `hasResults` with `setDataValue`.

## Reading results from robot code

{% tabs %}
{% tab title="Java" %}
```java
import java.util.Optional;
import synapse.SynapseCamera;
import synapse.SynapsePipelineType;
import synapse.pipelines.apriltag.ApriltagResult;

SynapseCamera camera = new SynapseCamera("camera0", "Synapse");

if (camera.getPipelineType().equals(SynapsePipelineType.kApriltag.typestring)) {
  Optional<ApriltagResult> results =
      camera.getResults(SynapsePipelineType.kApriltag);

  results.ifPresent(r -> {
    for (var tag : r.tags) {
      System.out.println("Tag " + tag.tagID + " hamming " + tag.hamming);
    }
  });
}
```
{% endtab %}

{% tab title="Python" %}
```python
from synapselib import SynapseCamera
from synapselib.pipelines.apriltag import ApriltagResult

camera = SynapseCamera("camera0", "Synapse")

data = camera.getResultsEntry().getRaw(b"")
results = camera.getResults(ApriltagResult, data)

if results is not None:
    for tag in results.tags:
        print(f"Tag {tag.tag_id} hamming {tag.hamming}")
```
{% endtab %}
{% endtabs %}

### Custom result types in robot code

{% tabs %}
{% tab title="Java" %}
```java
import com.fasterxml.jackson.core.type.TypeReference;
import synapse.SynapsePipelineType;

public static final SynapsePipelineType<MyPipelineResult> kMyPipeline =
    new SynapsePipelineType<>(
        new TypeReference<MyPipelineResult>() {},
        "MyPipeline");

Optional<MyPipelineResult> results = camera.getResults(kMyPipeline);
```
{% endtab %}

{% tab title="Python" %}
```python
from dataclasses import dataclass
from synapselib import SynapsePipelineType

@dataclass
class MyPipelineResult:
    count: int
    label: str
    confidence: float

kMyPipeline = SynapsePipelineType(MyPipelineResult, "MyPipeline")

data = camera.getResultsEntry().getRaw(b"")
results = camera.getResults(kMyPipeline.getResultType(), data)
```
{% endtab %}
{% endtabs %}

The type string is mostly informational, but it should match the pipeline type name so you can use `getPipelineType()` to check which pipeline is running.

## Inspecting results in the dashboard

Open the dashboard and select the camera and pipeline. The results panel shows:

- **Final results** as an expandable MessagePack tree.
- **Auxiliary values** as a key/value table.

If the panel is empty, the pipeline has not published anything yet, or the active pipeline is not the one you expect.

## Next steps

- [Custom Pipelines](README.md)
- [Settings API](settings-api.md)
- [Custom Pipeline Data](../../robot-interfacing/synapse-bridge/custom-pipeline-data.md)
- [NetworkTables API](../../additional-resources/networktables-api.md)
