---
description: Known bugs, limitations, and workarounds in the current release.
icon: bug
---

# Known Issues

These issues are present in the current codebase. Each entry includes a workaround where one exists.

{% hint style="info" %}
Found an issue that is not listed here? Open an issue on [GitHub](https://github.com/DanPeled/Synapse/issues) with your runtime version and logs.
{% endhint %}

## 2027 alpha Java vendordep is not published

**Affects:** Java robot projects using the 2027 alpha

The `v2027.0.0a1` release notes link to `SynapseLib-2027.0.0a1.json`, but that file and the matching `2027.0.0a1` Maven artifacts are not published on GitHub Pages yet.

**Workaround:** Use the current `SynapseLib-dev.json` vendordep described in [Installing SynapseLib](../robot-interfacing/synapse-bridge/installing-synapse-bridge.md). It tracks the 2027 alpha code but may change between builds. Re-check for a pinned vendordep before relying on it for a season release.

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

## Synapse Manager cannot trust a new SSH host key

**Affects:** Deploying from Synapse Manager to a device that is not already in `~/.ssh/known_hosts`

The installer verifies SSH host keys. Synapse Manager runs `synapse_installer install` without a terminal, so the installer cannot show the fingerprint prompt and rejects an unknown key.

**Workaround:** Run the deploy once from a terminal, or connect with `ssh <user>@<device-ip>`, and accept the fingerprint. After the key is in `~/.ssh/known_hosts`, deploy from Synapse Manager normally.

## Automatic discovery can report `127.0.0.1`

**Affects:** `python -m synapse_installer device add` → **Automatic** on a device that cannot determine its outbound network address

The runtime reports the address of the interface it would use to reach the internet. If it cannot determine one, it falls back to `127.0.0.1`. The installer accepts that value and saves it as the device IP, so deploys to that entry fail.

**Workaround:** Add the device manually with its real IP address.

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

## Unused AprilTag settings

**Affects:** AprilTag settings panel

- `iteration_count` is commented out of the settings class, so it cannot be set.
- `publish_tag_pose_3d` is defined but never used; tag 3D poses are not included in results.
- `verbosity` is defined but the filtering helper is never called; changing it has no effect.

**Workaround:** None. Do not rely on these settings.

## Cropping shifts the AprilTag pose

**Affects:** `ApriltagPipeline` with `crop_x` / `crop_y` set to anything other than `[-1, 1]`

The pipeline crops the frame before running the detector, so tag corners are measured in the cropped image. Pose estimation still uses the full-frame camera matrix because the setting-change handler never applies the crop offset. A crop that is not centered on the camera's principal point therefore shifts the estimated camera pose.

**Workaround:** Leave the crop at `[-1, 1]` when you rely on field localization, or keep the crop centered on the image and generous enough that the offset is small. Cropping still works normally for detection-only use.

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

## Next steps

- [Troubleshooting](troubleshooting.md)
- [NetworkTables API](networktables-api.md)
- [Robot Pose](../robot-interfacing/synapse-bridge/robot-pose.md)
