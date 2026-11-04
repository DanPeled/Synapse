---
description: Write your own vision pipeline that runs inside the Synapse runtime.
icon: person-military-pointing
---

# Custom Pipelines

Synapse ships with built-in pipelines, but you can also write your own. A custom pipeline is a Python class that receives every camera frame, runs your code, and returns the frame to display.

Custom pipelines are useful for:

- Detecting game pieces that the built-in pipelines do not handle.
- Running a custom model or algorithm.
- Drawing overlays for drivers.
- Publishing your own results to robot code.

{% hint style="info" %}
This section explains how to plug a class into Synapse. It is not a tutorial on computer vision. For OpenCV itself, see the [OpenCV Python tutorials](https://docs.opencv.org/4.x/d6/d00/tutorial_py_root.html).
{% endhint %}

## How Synapse finds pipelines

Synapse scans the project for files matching:

```text
**/*_pipeline.py
```

The search is recursive, so a file anywhere in the project is found as long as its name ends in `_pipeline.py`. Files named `setup.py` are skipped.

Every class in those files that subclasses `Pipeline` is registered. The class name becomes the pipeline type shown in the dashboard unless you rename it with a decorator.

{% hint style="warning" %}
Pipeline files are loaded when the runtime starts. After adding, deleting, or renaming a pipeline file, restart the runtime so the change appears in the dashboard.
{% endhint %}

## A minimal pipeline

Create a file such as `pipelines/my_pipeline.py`:

```python
from synapse import Pipeline
from synapse.stypes import Frame


class MyPipeline(Pipeline):
    def __init__(self, settings):
        super().__init__(settings)

    def processFrame(self, img: Frame, timestamp: float) -> Frame:
        # Called once per camera frame.
        return img
```

That is enough for the pipeline to appear in the dashboard.

{% hint style="warning" %}
Call `super().__init__(settings)` in your constructor. The base class sets up settings, camera bindings, and NetworkTables publishing. Skipping it breaks the pipeline.
{% endhint %}

## What `processFrame` receives

| Argument | Type | Meaning |
| --- | --- | --- |
| `img` | `Frame` (a NumPy BGR image) | The current camera frame |
| `timestamp` | `float` | The runtime's processing start time, in seconds |

Return:

- The processed frame to show in the dashboard and publish to the camera stream.
- `None` to keep the previous frame.

The frame is a normal NumPy array, so you can use OpenCV, NumPy, or any Python image library directly.

```python
import cv2
from synapse import Pipeline
from synapse.stypes import Frame


class GrayPipeline(Pipeline):
    def __init__(self, settings):
        super().__init__(settings)

    def processFrame(self, img: Frame, timestamp: float) -> Frame:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
```

## Adding settings

Define a settings class that subclasses `PipelineSettings`, then pass it as the generic argument to `Pipeline`:

```python
from synapse import Pipeline, PipelineSettings
from synapse.core.settings_api import NumberConstraint, settingField
from synapse.stypes import Frame


class MyPipelineSettings(PipelineSettings):
    circle_size = settingField(
        NumberConstraint(minValue=0, maxValue=None),
        default=20,
        description="Radius of the circle in pixels.",
        category="<Circle/> Drawing",
    )

    circle_x = settingField(
        NumberConstraint(minValue=0, maxValue=1920, step=1),
        default=960,
        description="Circle center X in pixels.",
        category="<Circle/> Drawing",
    )

    circle_y = settingField(
        NumberConstraint(minValue=0, maxValue=1080, step=1),
        default=540,
        description="Circle center Y in pixels.",
        category="<Circle/> Drawing",
    )


class MyPipeline(Pipeline[MyPipelineSettings]):
    def __init__(self, settings: MyPipelineSettings):
        super().__init__(settings)

    def processFrame(self, img: Frame, timestamp: float) -> Frame:
        size = int(self.getSetting(MyPipelineSettings.circle_size))
        x = int(self.getSetting(MyPipelineSettings.circle_x))
        y = int(self.getSetting(MyPipelineSettings.circle_y))

        return cv2.circle(img, (x, y), size, (0, 255, 0), thickness=2)
```

Settings are validated automatically. The dashboard generates a slider, toggle, dropdown, and so on from the constraint.

You can read a setting by its `Setting` object or by its key string:

```python
value = self.getSetting(MyPipelineSettings.circle_size)
value = self.getSetting("circle_size")
```

{% hint style="info" %}
See [Settings API](settings-api.md) for every constraint type, descriptions, and categories.
{% endhint %}

## Reacting to setting changes

Override `onSettingChanged` if your pipeline needs to rebuild something when a value changes, such as a lookup table or a model input size:

```python
def onSettingChanged(self, setting, value) -> None:
    if setting.key == "circle_size":
        print(f"Circle size is now {value}")
```

The base method does nothing, so calling `super().onSettingChanged(...)` is optional.

## Naming and hiding pipelines

Use decorators from `synapse.core.pipeline` to control how a pipeline appears.

### Rename a pipeline type

```python
from synapse.core.pipeline import pipelineName


@pipelineName("My Awesome Pipeline")
class MyPipeline(Pipeline):
    ...
```

Without a decorator, the type name is the class name (`MyPipeline`).

### Mark a system pipeline

```python
from synapse.core.pipeline import systemPipeline


@systemPipeline()
class MyInternalPipeline(Pipeline):
    ...
```

System pipelines get a name wrapped in `$$`, for example `$$MyInternalPipeline$$`. Synapse uses this for built-in pipelines such as calibration and the driver view. You normally do not need it.

### Hide a pipeline

```python
from synapse.core.pipeline import disabled


@disabled
class WorkInProgressPipeline(Pipeline):
    ...
```

A disabled pipeline is still imported, but it is not registered, so it does not appear in the dashboard.

## Lifecycle

Synapse creates one pipeline instance per camera and pipeline slot.

| Stage | What happens |
| --- | --- |
| `__init__(settings)` | Synapse creates the pipeline and passes the settings object |
| `bind(cameraIndex, camera)` | Synapse attaches the pipeline to a camera and loads its camera properties |
| `processFrame(img, timestamp)` | Runs once per frame |
| `onSettingChanged(setting, value)` | Runs when a setting is changed |

If you override `bind`, call `super().bind(cameraIndex, camera)` first so the camera settings are loaded.

## Camera settings and calibration

Every pipeline has access to the camera's hardware settings and calibration data.

```python
from synapse.core.settings_api import CameraSettings

resolution = self.getCameraSetting(CameraSettings.resolution)
matrix = self.getCameraMatrix(self.cameraIndex)
distortion = self.getDistCoeffs(self.cameraIndex)
```

| Method | Returns |
| --- | --- |
| `getCameraSetting(key)` | A camera property such as `resolution` or `exposure` |
| `setCameraSetting(key, value)` | Updates a camera property |
| `getCameraSettings()` | The full `CameraSettings` collection |
| `getCameraMatrix(cameraIndex)` | The 3×3 camera matrix for the current resolution |
| `getDistCoeffs(cameraIndex)` | The lens distortion coefficients |
| `getResolution()` | The current resolution as `(width, height)` |

If the current resolution has no calibration entry, `getCameraMatrix` scales the nearest calibration it can find and logs a warning. Recalibrate at the resolution you actually use for the best results.

## Sending data to robot code

Pipelines can publish two kinds of data:

- **Final results** with `self.setResults(...)`, encoded as MessagePack.
- **Auxiliary values** with `self.setDataValue(key, value)`, published as normal NetworkTables values.

See [Sending Results](sending-results.md) for the full API.

## Complete example

```python
import cv2
from synapse import Pipeline, PipelineSettings
from synapse.core.settings_api import NumberConstraint, settingField
from synapse.stypes import Frame


class CircleSettings(PipelineSettings):
    radius = settingField(
        NumberConstraint(minValue=1, maxValue=500, step=1),
        default=60,
        description="Circle radius in pixels.",
        category="<Circle/> Drawing",
    )
    thickness = settingField(
        NumberConstraint(minValue=1, maxValue=20, step=1),
        default=3,
        description="Circle outline thickness.",
        category="<Circle/> Drawing",
    )


class CirclePipeline(Pipeline[CircleSettings]):
    def __init__(self, settings: CircleSettings):
        super().__init__(settings)

    def processFrame(self, img: Frame, timestamp: float) -> Frame:
        height, width = img.shape[:2]
        radius = int(self.getSetting(CircleSettings.radius))
        thickness = int(self.getSetting(CircleSettings.thickness))

        return cv2.circle(
            img,
            (width // 2, height // 2),
            radius,
            (0, 255, 0),
            thickness,
        )
```

## Common mistakes

| Problem | Cause |
| --- | --- |
| Pipeline does not appear | The file name does not end in `_pipeline.py` |
| Pipeline does not appear after editing | The runtime was not restarted |
| `TypeError` about settings | `super().__init__(settings)` was not called |
| Import error for `Pipeline` | Use `from synapse import Pipeline`, not a different package |
| Settings show old values | Press **Save** in the dashboard after changing them |
| `getSetting` returns `None` | The key does not exist in the settings class |

## Next steps

- [Settings API](settings-api.md)
- [Sending Results](sending-results.md)
- [Accessing Global Settings](accessing-global-settings.md)
- [Custom Pipeline Data](../../robot-interfacing/synapse-bridge/custom-pipeline-data.md)
