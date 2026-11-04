---
description: Known bugs, limitations, and workarounds in the current release.
icon: bug
---

# Known Issues

These issues are present in the current codebase. Each entry includes a workaround where one exists.

{% hint style="info" %}
Found an issue that is not listed here? Open an issue on [GitHub](https://github.com/DanPeled/Synapse/issues) with your runtime version and logs.
{% endhint %}

## Generated `main.py` has a broken import

**Affects:** New projects created with `python -m synapse_installer create`

The generated `main.py` contains:

```python
from synapse.core import Synapse
```

`synapse/core/__init__.py` is empty, so this import raises `ImportError`.

**Workaround:** Change the import to:

```python
from synapse.core.synapse import Synapse
```

## `sync` and `install` need an explicit device name

**Affects:** `python -m synapse_installer sync` and `install` without a device name

When no device name is passed, `sync` falls back to the installer process's `sys.argv` instead of the devices in `.synapseproject`. It then reports `No device named ... found` for each process argument and does not sync dependencies. `install` still runs `deploy`, so files may be uploaded without the Python environment being prepared.

**Workaround:** Pass the device nickname (the key under `deploy` in `.synapseproject`):

```bash
python -m synapse_installer install orangepi
```

`deploy` without a name still targets every configured device.

## Python cannot deserialize nested results

**Affects:** `synapselib` users reading `ApriltagResult` or `ColorResult`

The Python MessagePack decoder applies the top-level result class to every nested dictionary. A `tags` list is deserialized as a list of `ApriltagResult` objects with empty fields, not `ApriltagDetection` objects.

**Workaround:** Decode to plain dictionaries with `msgpack`:

```python
import msgpack

raw = camera.getResultsEntry().getRaw(b"")
data = msgpack.loads(raw, raw=False)

for tag in data["tags"]:
    print(tag["tag_id"], tag["tagPose_screenSpace"])
```

Flat result classes with no nested dataclasses deserialize correctly. Java is not affected.

## Camera settings are not published to NetworkTables by default

**Affects:** `SynapseCamera.getSetting` / `setSetting` in both languages

The runtime starts with settings publishing disabled. The `settings/` subtable is not populated, so typed setting reads return `None` and writes cannot reach the runtime.

**Workaround:** Use the dashboard for settings, or start the runtime with publishing enabled:

```python
from pathlib import Path
from synapse.core.synapse import Synapse

Synapse.createAndRunRuntime(root=Path.cwd(), sendSettingsInNT=True)
```

See [Runtime Camera Settings](../robot-interfacing/synapse-bridge/runtime-camera-settings.md).

## AprilTag `critical_angle` is treated as radians

**Affects:** AprilTag detection filtering

The setting is labeled `0–90` and defaults to `45`, but it is passed directly to WPILib's `criticalAngle`, which expects **radians**. The effective value is about 45 radians, so the angle rejection is effectively disabled.

**Workaround:** Until this is fixed, enter the value in radians. For 45°, use `0.785`.

## Disabling `publish_camera_field_pose` breaks result serialization

**Affects:** AprilTag pipeline when `publish_camera_field_pose = False`

The result serializer reads `result.cameraPoseEstimate.cameraPoseEstimate` without checking for `None`. When field pose publishing is disabled, serialization raises an exception and no results are sent.

**Workaround:** Keep `publish_camera_field_pose` enabled (the default).

## Unused AprilTag settings

**Affects:** AprilTag settings panel

- `iteration_count` is commented out of the settings class, so it cannot be set.
- `publish_tag_pose_3d` is defined but never used; tag 3D poses are not included in results.
- `verbosity` is defined but the filtering helper is never called; changing it has no effect.

**Workaround:** None. Do not rely on these settings.

## Python `tx` / `ty` are inconsistent

**Affects:** `synapselib.pipelines.apriltag.ApriltagDetection`

`tx` is a property, but `ty` is a method:

```python
x = tag.tx
y = tag.ty()
```

Java exposes both as methods: `tag.tx()` and `tag.ty()`.

**Workaround:** Use the attribute/method exactly as defined above.

## Java and Python orientation setting types differ

**Affects:** Predefined `Setting.kOrientation`

Java defines `kOrientation` as a `String` setting. Python defines it as an `Integer` setting. Reading one with the other's type returns nothing.

**Workaround:** Create the setting explicitly with the type the runtime publishes, or read the type first:

```python
from synapselib._synapse_camera import Setting
orientation = Setting.stringSetting("orientation")
```

## Capture latency is always zero

**Affects:** `captureLatency` / `getCaptureLatency()`

The runtime currently publishes `0.0` for capture latency. Process latency is measured correctly.

**Workaround:** None. Use process latency and FPS for performance tuning.

## Import Settings accepts JSON but only handles ZIP

**Affects:** Settings page → **Import Settings**

The file picker filters for `.json,.zip`, but the import handler only processes `.zip`. Selecting a JSON file produces an error.

**Workaround:** Export settings as a ZIP, then import that ZIP.

## Remove Camera is disabled

**Affects:** Camera page

The **Remove Camera** action is visible but disabled. Cameras cannot be removed from the dashboard in the current build.

**Workaround:** Edit the camera configuration on the device, or start from a fresh project.

## Windows camera performance

**Affects:** Windows runtimes

Camera performance may be significantly worse on Windows than on Linux. The cause is not confirmed; it may be related to the CSCore version in use.

**Workaround:** Use Linux for a coprocessor. Windows is fine for development and testing.

## Camera stream does not load after a restart

**Affects:** Dashboard camera stream

The stream occasionally fails to attach after restarting the runtime, likely due to a UI lifecycle issue.

**Workaround:** Refresh the browser tab. If that fails, navigate to the Camera page again.

## Slow shutdown on some systems

**Affects:** Ctrl+C / runtime shutdown

Shutdown can take a long time on some operating systems, though it is usually fast on a robot coprocessor.

**Workaround:** Wait for the process to exit. Avoid killing it mid-write, especially while settings are being saved.

## Next steps

- [Troubleshooting](troubleshooting.md)
- [NetworkTables API](networktables-api.md)
- [Robot Pose](../robot-interfacing/synapse-bridge/robot-pose.md)
