---
description: Overview of the Results API and MsgPack data serialization
icon: binary-circle-check
---

# Sending Results

{% hint style="info" %}
This page is dedicated to explaining how to **send** results via the runtime, in order to learn how to recieve results and deserilize them, take a look at [synapse-bridge](../../robot-interfacing/synapse-bridge/ "mention")
{% endhint %}

## The Results API

To enable seamless communication between the UI, SynapseLib, and the pipeline’s data, the Results API was introduced. Its purpose is to simplify data exchange as much as possible.

Pipeline results are divided into two categories:&#x20;

* [**Final Results**](sending-results.md#final-results)**:** The final results from the pipeline (i.e tag data and robot pose estimation from the ApriltagPipeline), serialized into bytes using [MsgPack](https://msgpack.org/index.html). Not human readable in NT (The average human atleast).
* [**Auxiliary Results**](sending-results.md#primitive-type-results)**:** Additional data the pipeline may send to the user, dont have any serilization and are sent directly as their provided value. Human readable inside of NT.

### Primitive Type Results

Any primitive type (int, float, boolean, string, bytes) and their array variation, is supported by default to sending directly via their value and an identifying key (string) that will be send to the UI & SynapseLib, via the `setDataValue` method found on the `Pipeline` class.

```python
self.setDataValue("hasResults", False)
```

{% hint style="info" %}
Example usage for this can be found inside of the [ApriltagPipeline](https://github.com/DanPeled/Synapse/blob/main/synapse_core/src/synapse/pipelines/apriltag_pipeline.py) class
{% endhint %}

### Final Results

Final results for a pipeline **must** extend the `PipelineResult` class or be decorated with the `@pipelineResult` decorator which will make it both a `dataclass` and extend the `PipelineResult` class automatically

Example class:

```python
from synapse.core.pipeline import pipelineResult

@pipelineResult
class MyPipelineResults:
    fun: int
    happiness: str
    position: float
```

Then, a result class instance can be sent directly via the `setResults` method, which will automatically recursivly find all the variables inside of the `PipelineResult` and send them to the UI & NT, serlialized into bytes.

### Defining Robot-Code Results Class

Coming soon...
