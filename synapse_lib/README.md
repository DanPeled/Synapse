# SynapseLib

Robot-side Java and Python clients for the Synapse vision runtime.

SynapseLib reads camera settings and pipeline results over NetworkTables. It
ships typed models for the built-in pipelines and lets teams define their own
result types without modifying the library.

## Install

- **Java:** add the SynapseLib vendor dependency to your robot project.
- **Python:** `pip install synapsefrclib`

## Quick start

### Python

```python
from synapselib import SynapseCamera, SynapsePipelineType

camera = SynapseCamera("MyCamera")  # uses the "Synapse" coprocessor table
camera.setPipeline(1)
camera.setRecordStatus(True)

result = camera.getLatestResults(SynapsePipelineType.kColor)
```

### Java

```java
import synapse.SynapseCamera;
import synapse.SynapsePipelineType;
import synapse.pipelines.color.ColorResult;

SynapseCamera camera = new SynapseCamera("MyCamera");
camera.setPipeline(1);
camera.setRecordStatus(true);

camera
    .getResults(SynapsePipelineType.kColor)
    .ifPresent(result -> System.out.println(result.timestamp));
```

## Camera API

`SynapseCamera` exposes the runtime's NetworkTables values:

- `getPipeline()` / `setPipeline(int)`
- `getPipelineType()`
- `getRecordingStatus()` / `setRecordStatus(boolean)`
- `getCaptureLatency()` / `getProcessLatency()` (seconds)
- `getSetting(Setting<T>)` / `setSetting(Setting<T>, T)`
- `getResults(...)` for a typed pipeline result

Topics and settings are available as constants on
`SynapseCamera.NetworkTableTopics` and `SynapseCamera.Setting`. The Python
client exposes the same values on `SynapseCamera.NetworkTableTopics` and
`Setting`.

## Custom pipelines

Custom result types are supported. Define a class that matches the payload
your pipeline publishes, then construct a pipeline type with it:

```python
from dataclasses import dataclass
from synapselib import SynapseCamera, SynapsePipelineType

@dataclass
class MyResult:
    timestamp: float
    label: str

myPipeline = SynapsePipelineType(MyResult, "MyPipeline")
camera.getLatestResults(myPipeline)
```

The Java equivalent accepts a Jackson `TypeReference`:

```java
SynapsePipelineType<MyResult> myPipeline =
    new SynapsePipelineType<>(new TypeReference<MyResult>() {}, "MyPipeline");
```

## Generated sources

NetworkTables paths, camera settings, and built-in pipeline type strings are
derived from the `synapse_core` runtime source. The built-in result models live
in `schema/synapse_lib.json` and are shared by the Java and Python generators.

Regenerate after changing either side:

```bash
python tools/generate_synapse_lib.py
```

Check for drift without writing files:

```bash
python tools/generate_synapse_lib.py --check
```

Use `--no-runtime` to render from the committed schema without reading
`synapse_core` (for example, when building the library on its own).
