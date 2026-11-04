---
description: How pipeline settings are generated, grouped, validated, and saved in the dashboard.
icon: sliders-up
---

# Pipeline Settings

Every pipeline in the dashboard has a settings panel. Synapse generates the controls from the settings class in Python, so the panel always matches the code that is running.

This page explains how the panel works. For the settings of a specific pipeline, see:

- [ApriltagPipeline Settings](../built-in-pipelines/apriltag-pipeline/apriltagpipeline-settings.md)
- [Color Detection Pipeline](../built-in-pipelines/color-detection-pipeline.md)

## Where settings live

Settings are split into two groups:

| Group | Defined by | Example keys |
| --- | --- | --- |
| **Pipeline settings** | The pipeline's settings class | `tag_size`, `crop_x`, `min_area` |
| **Camera properties** | The camera driver and `CameraSettings` | `brightness`, `exposure`, `orientation`, `resolution` |

Both are shown in the same panel, grouped by category. Pipeline settings appear first, then the **Camera Properties** category.

## Categories

Settings are grouped into tabs by their `category` argument:

```python
tag_size = settingField(
    NumberConstraint(minValue=0, maxValue=None),
    default=0.1651,
    description="Physical size of the AprilTag in meters.",
    category="<Toolbox/> Target",
)
```

The text after `/>` is the category label, and the value inside `<.../>` is a Lucide icon name. The example renders a `Target` tab with a toolbox icon.

If a setting has no category, it appears in the default group.

## Controls

The dashboard chooses a control from the setting's constraint:

| Constraint | Control |
| --- | --- |
| `NumberConstraint` with both min and max | Slider |
| `NumberConstraint` without min or max | Number input |
| `BooleanConstraint` | Toggle |
| `BooleanConstraint(renderAsButton=True)` | Button |
| `EnumeratedConstraint` | Dropdown |
| `StringConstraint` | Text input |
| `RangeConstraint` | Two-handle range slider |
| `ColorConstraint` | Color picker |
| `FileConstraint` | File picker |
| `ListConstraint` | List editor |

For more about constraints, see [Settings API](../custom-pipelines/settings-api.md).

## Changing a setting

1. Select a camera.
2. Select the pipeline you want to tune.
3. Open the category tab that contains the setting.
4. Change the value.

Changes are applied to the running pipeline immediately. That means you can watch the camera stream and the results panel update as you drag a slider.

{% hint style="warning" %}
Changing a setting in the browser does not automatically save it to disk. Press **Save** to persist the value. If the runtime restarts before you save, the previous value is restored.
{% endhint %}

## Save

Press **Save** in the dashboard's action card to write the current settings to the device.

Saving writes:

- Pipeline settings to `config/camera_<index>/pipeline_settings.yml`.
- Camera properties to `config/camera_<index>/camera_configs.yml`.

Because deploys preserve the `config/` folder, saved settings survive a redeploy.

## Lock

Press **Lock** to make the settings controls read-only. Locking does not stop the pipeline and does not prevent robot code or NetworkTables from changing settings. It only prevents accidental changes from the browser.

Press **Unlock** to edit again.

## Record

Press **Record** to start or stop recording the selected camera stream.

{% hint style="info" %}
Recordings are written to the device and can fill the SD card quickly. Check free space in the [Settings Page](settings-page.md) before recording for a long time.
{% endhint %}

## Results panel

The results panel below the stream shows the latest pipeline output.

- **Final results** are MessagePack-encoded and displayed as an expandable tree.
- **Auxiliary values** are displayed in a table. These are the values the pipeline sends with `setDataValue`.

Use the copy buttons to copy a value to the clipboard. This is handy for checking a pose, a pixel coordinate, or a reprojection error.

If the panel is empty:

- The pipeline may not have run yet.
- The pipeline may not have produced a result (for example, no tags are visible).
- The active pipeline may be different from the one you expect.

## Camera properties

The **Camera Properties** category controls the physical camera:

| Setting | What it does |
| --- | --- |
| `brightness` | Image brightness |
| `saturation` | Color intensity |
| `sharpness` | Edge sharpness |
| `gain` | Signal amplification |
| `orientation` | Rotates the image by 0°, 90°, 180°, or 270° |
| `resolution` | Capture resolution |

The available range for the driver settings comes from the camera itself, so it may differ between cameras. The resolution list only contains modes the camera reports as supported.

Additional driver properties may appear automatically. Synapse skips noisy or internal properties such as `raw`, `backlight`, `gamma`, and `exposure_dynamic_framerate`.

{% hint style="tip" %}
If you change **resolution**, recalibrate the camera at the new resolution. Calibration is stored per resolution.
{% endhint %}

## Next steps

- [Camera Page](camera-page.md)
- [Settings Page](settings-page.md)
- [Custom Pipelines](../custom-pipelines/README.md)
- [How Synapse Works](../../getting-started/how-synapse-works.md)
