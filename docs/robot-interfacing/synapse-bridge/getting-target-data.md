---
description: Create a SynapseCamera and read AprilTag or color detection results.
icon: crosshairs
---

# Getting Target Data

`SynapseCamera` is the main SynapseLib class. It represents one camera on one Synapse device and exposes its results, pipeline state, and metadata.

## Constructing a camera

{% tabs %}
{% tab title="Java" %}
```java
import synapse.SynapseCamera;

// Use the default root table name, "Synapse"
SynapseCamera camera = new SynapseCamera("camera0");

// Or specify the root table explicitly
SynapseCamera camera = new SynapseCamera("camera0", "Synapse");
```
{% endtab %}

{% tab title="Python" %}
```python
from synapselib import SynapseCamera

# Use the default root table name, "Synapse"
camera = SynapseCamera("camera0")

# Or specify the root table explicitly
camera = SynapseCamera("camera0", "Synapse")
```
{% endtab %}
{% endtabs %}

| Argument | Meaning |
| --- | --- |
| `cameraName` | The camera nickname from the Synapse dashboard |
| `coprocessorName` | The NetworkTables root table. Defaults to `Synapse` |

The camera name is the subtable name, so a mismatch means no data. You can verify it in the dashboard's Camera page.

{% hint style="info" %}
The root table is set on the runtime's **Settings** page as **NetworkTable**. If you changed it from `Synapse`, pass the new name to the constructor.
{% endhint %}

## Checking the active pipeline

The runtime publishes the active pipeline type as a string:

```java
if (camera.getPipelineType().equals(SynapsePipelineType.kApriltag.typestring)) {
  // AprilTag pipeline is active
}
```

```python
from synapselib import SynapsePipelineType

if camera.getPipelineType() == SynapsePipelineType.kApriltag.typestring:
    pass  # AprilTag pipeline is active
```

For a custom pipeline, the string is its pipeline type name, such as `MyPipeline`. Use this check before reading results so you do not try to decode one pipeline's bytes as another pipeline's result.

## Reading results

Java reads the latest published result with `getResults(pipelineType)`. Python provides the convenience method `getLatestResults(pipelineType)`, which reads `data/results` and decodes it for you.

{% tabs %}
{% tab title="Java" %}
```java
import java.util.Optional;
import synapse.SynapsePipelineType;
import synapse.pipelines.apriltag.ApriltagResult;

Optional<ApriltagResult> results =
    camera.getResults(SynapsePipelineType.kApriltag);

if (results.isPresent()) {
  ApriltagResult result = results.get();
  System.out.println("Tags: " + result.tags.length);
}
```
{% endtab %}

{% tab title="Python" %}
```python
from synapselib import SynapsePipelineType

results = camera.getLatestResults(SynapsePipelineType.kApriltag)

if results is not None:
    print(f"Tags: {len(results.tags)}")
```
{% endtab %}
{% endtabs %}

Java returns an `Optional<T>` that is empty when no bytes have been published. Python returns the decoded result, or `None` when no result is available.

{% hint style="info" %}
Python still exposes `getResults(resultType, data)` if you already have raw MessagePack bytes. `getLatestResults(pipelineType)` is the shorter form for reading and decoding the current entry.
{% endhint %}

## AprilTag results

{% tabs %}
{% tab title="Java" %}
`ApriltagResult`:

| Field / method | Type | Meaning |
| --- | --- | --- |
| `tags` | `ApriltagDetection[]` | Detected tags |
| `cameraEstimate_fieldSpace` | `double[]` or `null` | Camera pose `[x, y, z, roll, pitch, yaw]` |
| `reprojectionError` | `double` | Pose fit error; lower is better. `0.0` when no pose is available |
| `cameraEstimate_fieldSpace3d()` | `Pose3d` or `null` | Camera pose as a WPILib pose |

`ApriltagDetection`:

| Field / method | Type | Meaning |
| --- | --- | --- |
| `tagID` | `int` | Fiducial ID |
| `hamming` | `int` | Bit errors in the detection; lower is better |
| `tagPose_screenSpace` | `double[]` | Tag center `[x, y]` in image pixels |
| `tx()` | `double` | Horizontal pixel coordinate |
| `ty()` | `double` | Vertical pixel coordinate |
{% endtab %}

{% tab title="Python" %}
`ApriltagResult`:

| Field / property | Type | Meaning |
| --- | --- | --- |
| `tags` | `list[ApriltagDetection]` | Detected tags |
| `cameraEstimate_fieldSpace` | `list[float]` or `None` | Camera pose `[x, y, z, roll, pitch, yaw]` |
| `reprojection_error` | `float` | Pose fit error; lower is better. `0.0` when no pose is available |
| `cameraEstimate_fieldSpace3d` | `Pose3d` or `None` | Camera pose as a WPILib pose (property) |

`ApriltagDetection`:

| Field / property | Type | Meaning |
| --- | --- | --- |
| `tag_id` | `int` | Fiducial ID |
| `hamming` | `int` | Bit errors in the detection; lower is better |
| `tagPose_screenSpace` | `list[float]` | Tag center `[x, y]` in image pixels |
| `tx` | `float` | Horizontal pixel coordinate (property) |
| `ty` | `float` | Vertical pixel coordinate (property) |
{% endtab %}
{% endtabs %}

### Units and coordinate systems

- `cameraEstimate_fieldSpace` uses meters for translation and degrees for rotation.
- `cameraEstimate_fieldSpace3d()` (Java) and `cameraEstimate_fieldSpace3d` (Python) convert those degrees to radians and return a WPILib `Pose3d`. They return `null`/`None` if no pose was published.
- The pose is the **camera** pose in field space, not the robot pose. See [Robot Pose](robot-pose.md) to convert it.
- `tagPose_screenSpace` is in **image pixels**: `(0, 0)` is the top-left corner and `(width, height)` is the bottom-right. The center of a 1920×1080 frame is `(960, 540)`.

### Example: aim at a tag

This mirrors the `aimAtTarget` example. It reads the tag's horizontal screen position and turns toward it.

{% tabs %}
{% tab title="Java" %}
```java
int targetTagId = 1;
double turn = 0.0;

if (camera.getPipelineType().equals(SynapsePipelineType.kApriltag.typestring)) {
  var results = camera.getResults(SynapsePipelineType.kApriltag);

  if (results.isPresent()) {
    for (var tag : results.get().tags) {
      if (tag.tagID != targetTagId) {
        continue;
      }

      // Normalize the pixel X coordinate to [-1, 1] around the frame center.
      double halfWidth = 960.0; // half of 1920; match your pipeline resolution
      double error = (tag.tagPose_screenSpace[0] - halfWidth) / halfWidth;
      double deadband = 0.05;

      if (Math.abs(error) > deadband) {
        turn = 0.8 * error;
      }
      break;
    }
  }
}
```
{% endtab %}

{% tab title="Python" %}
```python
target_tag_id = 1
turn = 0.0

if camera.getPipelineType() == SynapsePipelineType.kApriltag.typestring:
    results = camera.getLatestResults(SynapsePipelineType.kApriltag)

    if results is not None:
        for tag in results.tags:
            if tag.tag_id != target_tag_id:
                continue

            # Normalize the pixel X coordinate to [-1, 1] around the frame center.
            half_width = 960.0  # half of 1920; match your pipeline resolution
            error = (tag.tagPose_screenSpace[0] - half_width) / half_width
            deadband = 0.05

            if abs(error) > deadband:
                turn = 0.8 * error
            break
```
{% endtab %}
{% endtabs %}

## Color detection results

{% tabs %}
{% tab title="Java" %}
`ColorResult`:

| Field | Type | Meaning |
| --- | --- | --- |
| `timestamp` | `float` | Frame timestamp in seconds |
| `detections` | `ColorDetection[]` | All detected regions |
| `main_detection` | `ColorDetection` | Best detection, or `null` |

`ColorDetection`:

| Field | Type | Meaning |
| --- | --- | --- |
| `bbox` | `float[]` | Bounding box `[x, y, width, height]` in pixels |
| `center` | `float[]` | Center `[x, y]` in pixels |
| `area` | `float` | Area in pixels squared |
{% endtab %}

{% tab title="Python" %}
`ColorResult`:

| Field | Type | Meaning |
| --- | --- | --- |
| `timestamp` | `float` | Frame timestamp in seconds |
| `detections` | `list[ColorDetection]` | All detected regions |
| `main_detection` | `ColorDetection or None` | Best detection |

`ColorDetection`:

| Field | Type | Meaning |
| --- | --- | --- |
| `bbox` | `list[float]` | Bounding box `[x, y, width, height]` in pixels |
| `center` | `list[float]` | Center `[x, y]` in pixels |
| `area` | `float` | Area in pixels squared |
{% endtab %}
{% endtabs %}

```java
Optional<ColorResult> color = camera.getResults(SynapsePipelineType.kColor);

color.ifPresent(result -> {
  if (result.main_detection != null) {
    System.out.println("Center: " + result.main_detection.center[0]);
  }
});
```

```python
from synapselib import SynapsePipelineType

color = camera.getLatestResults(SynapsePipelineType.kColor)

if color is not None and color.main_detection is not None:
    print(color.main_detection.center[0])
```

## Latency and recording

```java
double captureSeconds = camera.getCaptureLatency();
double processSeconds = camera.getProcessLatency();

if (!camera.getRecordingStatus()) {
  camera.setRecordStatus(true);
}
```

```python
capture_seconds = camera.getCaptureLatency()
process_seconds = camera.getProcessLatency()

if not camera.getRecordingStatus():
    camera.setRecordStatus(True)
```

Both latency values are in seconds. Capture latency is currently always reported as `0.0`. Process latency is the time the pipeline spent on the frame.

## Changing the active pipeline

```java
long current = camera.getPipeline();
camera.setPipeline(2);
```

```python
current = camera.getPipeline()
camera.setPipeline(2)
```

The index is the pipeline's position for that camera, not its type. Changing it switches the pipeline immediately, just like choosing one in the dashboard.

## Closing a camera (Java)

`SynapseCamera` implements `AutoCloseable` because it holds NetworkTables subscribers. Close it when you are done, especially in tests:

```java
try (SynapseCamera camera = new SynapseCamera("camera0")) {
  // use camera
}
```

## Next steps

- [Robot Pose](robot-pose.md)
- [Runtime Camera Settings](runtime-camera-settings.md)
- [Custom Pipeline Data](custom-pipeline-data.md)
- [NetworkTables API](../../additional-resources/networktables-api.md)
