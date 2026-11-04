---
description: Read shared camera configuration, calibration, and global settings from a pipeline.
icon: earth-europe
---

# Accessing Global Settings

`GlobalSettings` is a runtime-wide store shared by every pipeline and camera. Use it when your pipeline needs configuration that is not specific to one pipeline instance, such as camera calibration, camera names, or the default pipeline for a camera.

It exposes:

- The map of camera configurations.
- Each camera's calibration data.
- Camera name, device path, and stream resolution.
- The default pipeline index for each camera.
- Global settings from `config/settings.yml`.

## Import

```python
from synapse.core.global_settings import GlobalSettings
```

`GlobalSettings` uses a metaclass, so you call its methods on the class itself. Do not create an instance.

## Camera configurations

### Get one camera

```python
config = GlobalSettings.getCameraConfig(0)

if config is not None:
    print(config.name)
    print(config.defaultPipeline)
```

`getCameraConfig(cameraIndex)` returns a `CameraConfig` or `None` if the camera has no saved configuration.

### Check whether a camera exists

```python
if GlobalSettings.hasCameraData(0):
    ...
```

### Get every camera

```python
for camera_index, config in GlobalSettings.getCameraConfigMap().items():
    print(camera_index, config.name)
```

The map is keyed by `CameraID`, which is an integer alias.

## What a `CameraConfig` contains

| Field | Type | Meaning |
| --- | --- | --- |
| `name` | `str` | Camera nickname shown in the dashboard and used in NetworkTables |
| `id` | `str` | The device path or identifier reported by the OS |
| `defaultPipeline` | `int` | Pipeline index used when the runtime starts |
| `streamRes` | `(width, height)` | Resolution of the camera stream |
| `calibration` | `dict[str, CalibrationData]` | Calibration keyed by resolution string such as `"1280x720"` |

### Access calibration

```python
from synapse.core.settings_api import CameraSettings

config = GlobalSettings.getCameraConfig(self.cameraIndex)
resolution = self.getCameraSetting(CameraSettings.resolution)

if config is not None:
    calibration = config.calibration.get(resolution)
    if calibration is not None:
        print(calibration.matrix)
        print(calibration.distCoeff)
        print(calibration.meanErr)
        print(calibration.measuredRes)
```

`matrix` is a flat list of 9 values in row-major order:

```text
[fx,  0, cx,
  0, fy, cy,
  0,  0,  1]
```

`distCoeff` is the OpenCV distortion coefficient list, typically `[k1, k2, p1, p2, ...]`.

{% hint style="warning" %}
Calibration is per resolution. If the camera has no entry for the current resolution, handle the `None` case or fall back to another resolution. The helper `Pipeline.getCameraMatrix(cameraIndex)` already does a nearest-resolution fallback and logs a warning.
{% endhint %}

## Global settings

`GlobalSettings` also stores the values from `config/settings.yml` as a `SettingsCollection`.

```python
value = GlobalSettings.getSetting("some_key")
GlobalSettings.setSetting("some_key", 42)

if "some_key" in GlobalSettings:
    ...
```

You can also use dictionary-style access:

```python
value = GlobalSettings["some_key"]
GlobalSettings["some_key"] = 42
```

### Inspect everything

```python
print(GlobalSettings.toDict())
print(GlobalSettings.getMap())
```

| Method | Returns |
| --- | --- |
| `getSetting(key)` | The current value or `None` |
| `setSetting(key, value)` | Updates the in-memory value |
| `toDict()` | The current values as a dict |
| `getMap()` | The full internal settings map |
| `hasCameraData(index)` | Whether a camera config exists |
| `getCameraConfig(index)` | A single `CameraConfig` |
| `getCameraConfigMap()` | All `CameraConfig` objects by camera index |
| `setCameraConfig(index, config)` | Replaces the config for a camera in memory |

Changes made with `setSetting` are in memory. Saving to disk is handled by the runtime's normal configuration flow, not by `setSetting` itself.

## Practical example: use calibration in a pipeline

```python
import cv2
import numpy as np
from synapse import Pipeline
from synapse.core.global_settings import GlobalSettings
from synapse.core.settings_api import CameraSettings


class UndistortPipeline(Pipeline):
    def __init__(self, settings):
        super().__init__(settings)
        self._map1 = None
        self._map2 = None
        self._cached_resolution = None

    def _buildMaps(self, img):
        resolution = self.getCameraSetting(CameraSettings.resolution)
        if resolution == self._cached_resolution:
            return

        config = GlobalSettings.getCameraConfig(self.cameraIndex)
        if config is None:
            return

        calibration = config.calibration.get(resolution)
        if calibration is None:
            return

        matrix = np.array(calibration.matrix, dtype=np.float64).reshape(3, 3)
        distortion = np.array(calibration.distCoeff, dtype=np.float64)
        height, width = img.shape[:2]

        self._map1, self._map2 = cv2.initUndistortRectifyMap(
            matrix,
            distortion,
            None,
            matrix,
            (width, height),
            cv2.CV_16SC2,
        )
        self._cached_resolution = resolution

    def processFrame(self, img, timestamp):
        self._buildMaps(img)
        if self._map1 is None or self._map2 is None:
            return img
        return cv2.remap(img, self._map1, self._map2, cv2.INTER_LINEAR)
```

## Where camera configs come from

At startup, Synapse loads each camera's config from:

```text
config/camera_<index>/camera_configs.yml
```

The file contains the camera name, device ID, default pipeline, stream resolution, and the calibration entries. Because deploys preserve the remote `config/` folder, these values survive a redeploy.

## Next steps

- [Custom Pipelines](README.md)
- [Settings API](settings-api.md)
- [Camera Calibration](../../getting-started/quick-start/camera-calibration.md)
