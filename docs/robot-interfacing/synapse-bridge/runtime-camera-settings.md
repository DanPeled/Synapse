---
description: Switch pipelines and read or change camera settings from robot code.
icon: sliders
---

# Runtime Camera Settings

`SynapseCamera` can control the running pipeline and, when enabled, read and write camera settings over NetworkTables.

## Switching the active pipeline

Each camera has an ordered list of pipelines. The index is the pipeline's position in that list.

{% tabs %}
{% tab title="Java" %}
```java
long index = camera.getPipeline();
System.out.println("Active pipeline index: " + index);

camera.setPipeline(2);
```
{% endtab %}

{% tab title="Python" %}
```python
index = camera.getPipeline()
print(f"Active pipeline index: {index}")

camera.setPipeline(2)
```
{% endtab %}
{% endtabs %}

`setPipeline` switches the pipeline immediately, just like selecting it in the dashboard.

To check which **type** is running, use `getPipelineType()`:

```java
if (camera.getPipelineType().equals(SynapsePipelineType.kApriltag.typestring)) {
  // ...
}
```

```python
if camera.getPipelineType() == SynapsePipelineType.kApriltag.typestring:
    ...
```

## Typed settings

Camera settings are exposed as typed `Setting<T>` objects. Build one from the setting's key and NetworkTables type.

### Java

```java
import synapse.SynapseCamera;
import synapse.SynapseCamera.Setting;

// Predefined camera settings
Setting<Double> brightness = SynapseCamera.Setting.kBrightness;
Setting<Double> gain = SynapseCamera.Setting.kGain;
Setting<Double> exposure = SynapseCamera.Setting.kExposure;
Setting<Long> orientation = SynapseCamera.Setting.kOrientation;

// A setting from your pipeline's settings class
Setting<Double> tagSize = SynapseCamera.Setting.doubleSetting("tag_size");

// Read
camera.getSetting(tagSize).ifPresent(value -> {
  System.out.println("tag_size = " + value);
});

// Write
camera.setSetting(tagSize, 0.1651);
```

Available Java factories:

| Factory | Value type | NetworkTables type |
| --- | --- | --- |
| `doubleSetting(key)` | `Double` | `double` |
| `integerSetting(key)` | `Long` | `int` |
| `stringSetting(key)` | `String` | `string` |
| `doubleArraySetting(key)` | `double[]` | `double[]` |
| `stringArraySetting(key)` | `String[]` | `string[]` |
| `booleanSetting(key)` | `Boolean` | `boolean` |
| `integerArraySetting(key)` | `long[]` | `int[]` |
| `booleanArraySetting(key)` | `boolean[]` | `boolean[]` |
| `generic(key, type, ntType)` | Custom | Custom |

### Python

```python
from synapselib import SynapseCamera
from synapselib._synapse_camera import Setting

brightness = Setting.kBrightness
gain = Setting.kGain
exposure = Setting.kExposure
orientation = Setting.kOrientation

tag_size = Setting.doubleSetting("tag_size")

value = camera.getSetting(tag_size)
if value is not None:
    print(f"tag_size = {value}")

camera.setSetting(tag_size, 0.1651)
```

Available Python factories:

| Factory | Value type | NetworkTables type |
| --- | --- | --- |
| `doubleSetting(key)` | `float` | `double` |
| `integerSetting(key)` | `int` | `int` |
| `stringSetting(key)` | `str` | `string` |
| `doubleArraySetting(key)` | `list[float]` | `double[]` |
| `stringArraySetting(key)` | `list[str]` | `string[]` |
| `booleanSetting(key)` | `bool` | `boolean` |

## Where settings live

Settings are written under the camera's `settings` subtable:

```text
<networktable>/<camera>/settings/<key>
```

For example:

```text
Synapse/camera0/settings/tag_size
Synapse/camera0/settings/brightness
```

The key is exactly the attribute name in the settings class. Camera properties use their own keys such as `brightness`, `gain`, `exposure`, `orientation`, and `resolution`.

## Important: settings publishing is off by default

{% hint style="warning" %}
The standard Synapse launcher starts with settings publishing **disabled**. In that mode the `settings/` table is not populated, so `getSetting` returns `None` and `setSetting` cannot update the runtime. Use the dashboard to change settings, or enable publishing as shown below.
{% endhint %}

To enable settings over NetworkTables, start the runtime with `sendSettingsInNT=True`. In your project's `main.py`:

```python
import os
from pathlib import Path

from synapse.core.synapse import Synapse

if __name__ == "__main__":
    Synapse.createAndRunRuntime(root=Path(os.getcwd()), sendSettingsInNT=True)
```

{% hint style="info" %}
`Synapse` lives in `synapse.core.synapse`. Importing it from `synapse.core` does not work in the current release.
{% endhint %}

When enabled:

- The runtime publishes every pipeline and camera setting to `settings/`.
- Remote writes to those entries are validated and applied to the running pipeline.
- Changes are applied immediately but are **not** saved to disk until you press **Save** in the dashboard.

## Reading camera properties

The library provides predefined typed settings for common camera properties. A camera only publishes the properties its driver supports:

| Setting | Key | Java constant | Python constant | Value type |
| --- | --- | --- | --- | --- |
| Brightness | `brightness` | `Setting.kBrightness` | `Setting.kBrightness` | `Double` / `float` |
| Gain | `gain` | `Setting.kGain` | `Setting.kGain` | `Double` / `float` |
| Exposure | `exposure` | `Setting.kExposure` | `Setting.kExposure` | `Double` / `float` |
| Orientation | `orientation` | `Setting.kOrientation` | `Setting.kOrientation` | `Long` / `int` (degrees) |
| Contrast | `contrast` | `Setting.kContrast` | `Setting.kContrast` | `Double` / `float` |
| Saturation | `saturation` | `Setting.kSaturation` | `Setting.kSaturation` | `Double` / `float` |
| Hue | `hue` | `Setting.kHue` | `Setting.kHue` | `Double` / `float` |
| White balance temperature | `white_balance_temperature` | `Setting.kWhiteBalanceTemperature` | `Setting.kWhiteBalanceTemperature` | `Double` / `float` |
| Sharpness | `sharpness` | `Setting.kSharpness` | `Setting.kSharpness` | `Double` / `float` |
| Resolution | `resolution` | `Setting.stringSetting("resolution")` | `Setting.stringSetting("resolution")` | `String` / `str` |

```java
camera.getSetting(SynapseCamera.Setting.kBrightness)
    .ifPresent(b -> System.out.println("Brightness: " + b));
```

```python
brightness = camera.getSetting(Setting.kBrightness)
if brightness is not None:
    print(f"Brightness: {brightness}")
```

### Orientation

`kOrientation` is an integer setting in both APIs: `Setting<Long>` in Java and `Setting[int]` in Python. The runtime publishes degrees (`0`, `90`, `180`, or `270`). Use the predefined constant directly; do not read it as a string. `resolution` is the common camera property that uses a string setting.

## Latency and recording

```java
double capture = camera.getCaptureLatency(); // seconds
double process = camera.getProcessLatency(); // seconds

camera.setRecordStatus(true);
boolean recording = camera.getRecordingStatus();
```

```python
capture = camera.getCaptureLatency()  # seconds
process = camera.getProcessLatency()  # seconds

camera.setRecordStatus(True)
recording = camera.getRecordingStatus()
```

Capture latency is currently always `0.0`. Process latency is the time the pipeline spent on the last frame.

## Next steps

- [Getting Target Data](getting-target-data.md)
- [Settings API](../../usage/custom-pipelines/settings-api.md)
- [Pipeline Settings (UI)](../../usage/built-in-pipelines-1/pipeline-settings.md)
