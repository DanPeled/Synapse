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
import edu.wpi.first.networktables.NetworkTableEntry;
import synapse.SynapseCamera;

SynapseCamera camera = new SynapseCamera("camera0", "Synapse");
NetworkTable data = camera.getDataTable();

boolean hasResults = data.getEntry("hasResults").getBoolean(false);
long tagCount = data.getEntry("tagCount").getInteger(0);
double score = data.getEntry("score").getDouble(0.0);
String label = data.getEntry("label").getString("");
```
{% endtab %}

{% tab title="Python" %}
```python
from synapselib import SynapseCamera

camera = SynapseCamera("camera0", "Synapse")
data = camera.getDataTable()

has_results = data.getEntry("hasResults").getBoolean(False)
tag_count = data.getEntry("tagCount").getInteger(0)
score = data.getEntry("score").getDouble(0.0)
label = data.getEntry("label").getString("")
```
{% endtab %}
{% endtabs %}

Always pass a default value. If the pipeline has not published the key yet, the entry does not exist, and a read without a default returns an empty/zero value or raises depending on the API.

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
Use `deserializeResults` with the raw entry:

```java
import com.fasterxml.jackson.core.type.TypeReference;
import java.util.Optional;
import synapse.SynapseCamera;

public Optional<MyPipelineResult> readResults(SynapseCamera camera) {
  byte[] raw = camera.getDataTable()
      .getEntry("results")
      .getRaw(new byte[0]);

  if (raw.length == 0) {
    return Optional.empty();
  }

  return camera.deserializeResults(
      new TypeReference<MyPipelineResult>() {},
      raw);
}
```
{% endtab %}

{% tab title="Python" %}
```python
from synapselib import SynapseCamera

def read_results(camera: SynapseCamera):
    raw = camera.getResultsEntry().getRaw(b"")
    return camera.getResults(MyPipelineResult, raw)
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

raw = camera.getResultsEntry().getRaw(b"")
result = camera.getResults(kMyPipeline.getResultType(), raw)
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
    result = camera.getResults(kMyPipeline.getResultType(),
                               camera.getResultsEntry().getRaw(b""))
```
{% endtab %}
{% endtabs %}

## Nested results

Nested dataclasses work on the Java side as long as the classes have no-argument constructors and public fields or setters.

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

On the Java side:

```java
public class Target {
  public int id;
  public double x;
  public double y;
  public Target() {}
}

public class TargetResult {
  public Target[] targets;
  public int best_id;
  public TargetResult() {}
}
```

{% hint style="warning" %}
Python's `getResults` has a bug with nested dataclass lists. See [Known Issues](../../additional-resources/known-issues.md) for the workaround using `msgpack` directly.
{% endhint %}

## Listening for changes

Polling once per robot loop is usually enough and is the simplest approach:

```java
@Override
public void robotPeriodic() {
  boolean hasResults = camera.getDataTable()
      .getEntry("hasResults")
      .getBoolean(false);

  if (hasResults) {
    camera.getResults(kMyPipeline).ifPresent(this::useResult);
  }
}
```

```python
def robotPeriodic(self):
    has_results = camera.getDataTable().getEntry("hasResults").getBoolean(False)
    if has_results:
        raw = camera.getResultsEntry().getRaw(b"")
        result = camera.getResults(kMyPipeline.getResultType(), raw)
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
