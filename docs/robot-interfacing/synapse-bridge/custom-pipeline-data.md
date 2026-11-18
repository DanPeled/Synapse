---
description: Read custom pipeline results and auxiliary values from robot code.
icon: database
---

# Custom Pipeline Data

If you write a [custom pipeline](../../usage/custom-pipelines/README.md), you can read its output from robot code with the same pattern used for the built-in pipelines. There are two channels:

| Channel | Pipeline method | NetworkTables key | Encoding |
| --- | --- | --- | --- |
| Final results | `setResults(result)` | `<camera>/data/results` | MessagePack bytes |
| Auxiliary values | `setDataValue(key, value)` | `<camera>/data/<key>` | Native value |

## Reading auxiliary values

Auxiliary values are ordinary NetworkTables entries, so you can read them directly.

{% tabs %}
{% tab title="Java" %}
```java
import edu.wpi.first.networktables.NetworkTable;
import edu.wpi.first.networktables.NetworkTableInstance;

NetworkTable data = NetworkTableInstance.getDefault()
    .getTable("Synapse")
    .getSubTable("camera0")
    .getSubTable("data");

boolean hasResults = data.getEntry("hasResults").getBoolean(false);
long tagCount = data.getEntry("tagCount").getInteger(0);
double score = data.getEntry("score").getDouble(0.0);
String label = data.getEntry("label").getString("");
```
{% endtab %}

{% tab title="Python" %}
```python
from ntcore import NetworkTableInstance

data = (
    NetworkTableInstance.getDefault()
    .getTable("Synapse")
    .getSubTable("camera0")
    .getSubTable("data")
)

has_results = data.getEntry("hasResults").getBoolean(False)
tag_count = data.getEntry("tagCount").getInteger(0)
score = data.getEntry("score").getDouble(0.0)
label = data.getEntry("label").getString("")
```
{% endtab %}
{% endtabs %}

Always pass a default value. If the pipeline has not published the key yet, the entry does not exist, and a read without a default returns an empty/zero value or raises depending on the API.

Java's `SynapseCamera.getDataTable()` is `protected`, so use the explicit table path shown above from robot code. For final results, prefer the public `getResults(...)` / `getLatestResults(...)` APIs below.

## Reading final results

Final results are MessagePack-encoded into `data/results`. You need a result class on the robot side that matches the field names from Python.

### Define the result class

{% tabs %}
{% tab title="Java" %}
```java
import com.fasterxml.jackson.annotation.JsonProperty;

public class MyPipelineResult {
  public int count;
  public String label;
  public double confidence;

  // Jackson needs a no-argument constructor
  public MyPipelineResult() {}

  @JsonProperty("best_id")
  public int bestId;
}
```
{% endtab %}

{% tab title="Python" %}
```python
from dataclasses import dataclass

@dataclass
class MyPipelineResult:
    count: int
    label: str
    confidence: float
    best_id: int
```
{% endtab %}
{% endtabs %}

Field names must match the serialized names exactly. In Java, use `@JsonProperty("python_name")` when the Java field name differs.

### Decode the bytes

{% tabs %}
{% tab title="Java" %}
Use `getResults` with a reusable `SynapsePipelineType` (defined below):

```java
import java.util.Optional;
import synapse.SynapseCamera;

public Optional<MyPipelineResult> readResults(SynapseCamera camera) {
  return camera.getResults(kMyPipeline);
}
```

If you need the raw bytes, read `<camera>/data/results` from an explicit NetworkTables table and pass them to `deserializeResults`.
{% endtab %}

{% tab title="Python" %}
```python
from synapselib import SynapseCamera, SynapsePipelineType

kMyPipeline = SynapsePipelineType(MyPipelineResult, "MyPipeline")

def read_results(camera: SynapseCamera):
    return camera.getLatestResults(kMyPipeline)
```
{% endtab %}
{% endtabs %}

You can also define a reusable `SynapsePipelineType`:

{% tabs %}
{% tab title="Java" %}
```java
import com.fasterxml.jackson.core.type.TypeReference;
import synapse.SynapsePipelineType;

public static final SynapsePipelineType<MyPipelineResult> kMyPipeline =
    new SynapsePipelineType<>(
        new TypeReference<MyPipelineResult>() {},
        "MyPipeline");

Optional<MyPipelineResult> result = camera.getResults(kMyPipeline);
```
{% endtab %}

{% tab title="Python" %}
```python
from synapselib import SynapsePipelineType

kMyPipeline = SynapsePipelineType(MyPipelineResult, "MyPipeline")

result = camera.getLatestResults(kMyPipeline)
```
{% endtab %}
{% endtabs %}

The type string should match the pipeline type shown in the dashboard. For a class named `MyPipeline`, that is `MyPipeline` unless you used `@pipelineName`.

## Matching the pipeline

`getResults` reads whatever is currently in `data/results`. If the camera switches to another pipeline, the bytes may belong to a different result class.

Check the active pipeline type first:

{% tabs %}
{% tab title="Java" %}
```java
if ("MyPipeline".equals(camera.getPipelineType())) {
  Optional<MyPipelineResult> result = camera.getResults(kMyPipeline);
}
```
{% endtab %}

{% tab title="Python" %}
```python
if camera.getPipelineType() == "MyPipeline":
    result = camera.getLatestResults(kMyPipeline)
```
{% endtab %}
{% endtabs %}

## Nested results

Nested result types are supported in both languages.

```python
from dataclasses import dataclass
from typing import Optional
from synapse.core.results_api import PipelineResult

@dataclass
class Target:
    id: int
    x: float
    y: float

@dataclass
class TargetResult(PipelineResult):
    targets: list[Target]
    best: Optional[Target] = None
    best_id: int = -1
```

On the Java side, use matching classes with no-argument constructors and public fields or setters:

```java
public class Target {
  public int id;
  public double x;
  public double y;
  public Target() {}
}

public class TargetResult {
  public Target[] targets;
  public Target best;
  public int best_id;
  public TargetResult() {}
}
```

Python's deserializer recursively converts nested dataclasses, lists, dictionaries, optionals, and WPILib geometry fields. Java uses Jackson with the WPILib geometry module registered, so the same nested payloads deserialize into matching Java classes. Field names must still match the serialized names, and missing fields fall back to defaults where available.

## Listening for changes

Polling once per robot loop is usually enough and is the simplest approach:

```java
NetworkTable data = NetworkTableInstance.getDefault()
    .getTable("Synapse")
    .getSubTable("camera0")
    .getSubTable("data");

@Override
public void robotPeriodic() {
  boolean hasResults = data.getEntry("hasResults").getBoolean(false);

  if (hasResults) {
    camera.getResults(kMyPipeline).ifPresent(this::useResult);
  }
}
```

```python
from ntcore import NetworkTableInstance

data = (
    NetworkTableInstance.getDefault()
    .getTable("Synapse")
    .getSubTable("camera0")
    .getSubTable("data")
)

def robotPeriodic(self):
    has_results = data.getEntry("hasResults").getBoolean(False)
    if has_results:
        result = camera.getLatestResults(kMyPipeline)
        if result is not None:
            self.use_result(result)
```

For lower latency, register a NetworkTables listener on the `data` table and process values in the callback. Keep the callback short and avoid blocking work.

## Naming checklist

| Place | Must match |
| --- | --- |
| Python result field | Java field or `@JsonProperty` name |
| Pipeline type string | Dashboard pipeline type |
| Camera name | Dashboard camera nickname |
| Root table | Settings page **NetworkTable** value |

## Next steps

- [Sending Results](../../usage/custom-pipelines/sending-results.md)
- [Custom Pipelines](../../usage/custom-pipelines/README.md)
- [NetworkTables API](../../additional-resources/networktables-api.md)
- [Known Issues](../../additional-resources/known-issues.md)
