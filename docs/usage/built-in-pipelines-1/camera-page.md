---
description: Inspect camera configuration, rename cameras, and calibrate or import calibration data.
icon: camera
---

# Camera Page

The Camera page shows the camera configuration and the calibration tools. Open it from the sidebar at `http://<device-ip>:3000`.

## Camera configuration

The **Camera Configuration** card shows one camera at a time. Use the **Camera** dropdown to switch cameras.

The card displays:

| Field | Meaning |
| --- | --- |
| **Camera Index** | The internal ID of the camera, starting at `0` |
| **Device UID** | The camera's system-level identifier, reported by the driver |
| **Stream Path** | The URL path where the runtime publishes the camera stream |
| **Default Pipeline** | The pipeline index and name used when the runtime starts |
| **Max FPS** | The maximum frame rate the camera is configured for |

{% hint style="info" %}
**Device UID** comes from the operating system. Some cameras allow you to change their device name or UID, which is useful when you connect two identical camera models.
{% endhint %}

### Rename a camera

1. Open the camera action menu next to the camera dropdown.
2. Choose **Rename**.
3. Enter a new name.
4. Press the check button.

The camera name is the NetworkTables subtable name used by robot code. If you rename a camera, update `new SynapseCamera("<camera-name>", ...)` in your robot code.

{% hint style="warning" %}
Renaming a camera changes the NetworkTables key, not the camera index. Settings and calibration stay attached to the index, so they are preserved.
{% endhint %}

### Remove a camera

The **Remove Camera** action is currently disabled. To remove a camera from a project, edit the camera configuration on the device or start from a fresh project.

## Camera calibration

Calibration measures the camera's lens distortion and focal length. It is required for accurate AprilTag pose estimates and recommended for any pipeline that maps pixels to positions.

1. Select the camera.
2. Choose the **resolution** you will use for vision.
3. Press **Calibrate**.
4. Follow the instructions in the calibration dialog.

The dialog lets you configure the Charuco board and capture images. Synapse shows a green check mark in the camera view when it can see enough board corners. Only capture an image when the check mark is visible.

{% hint style="warning" %}
Calibrate at the same resolution the pipeline uses. Calibration data is stored separately for each resolution.
{% endhint %}

For the full procedure, board defaults, and tips, see [Camera Calibration](../../getting-started/quick-start/camera-calibration.md).

## Import calibration results

If you calibrated the camera in another tool, you can import the result instead of recalibrating.

1. Export the calibration as JSON from a tool such as [CalibDB](https://calibdb.net/) or WPIcal.
2. Press **Import Results**.
3. Select the JSON file.

Synapse accepts the standard OpenCV-style calibration layout used by CalibDB and the flat layout used by WPIcal, with flexible key names. Imported data is applied to the selected camera and stored in the project config.

{% hint style="info" %}
The import is matched to the camera index and resolution in the file. If nothing changes after importing, check that the file contains a resolution the camera supports.
{% endhint %}

## How calibration is stored

Calibration is written to:

```text
config/camera_<index>/camera_configs.yml
```

Each resolution has its own entry containing:

- `matrix` — the camera matrix (focal length and principal point).
- `distCoeffs` — the distortion coefficients.
- `measured_res` — the resolution the calibration was measured at.
- `mean_err` — the mean reprojection error.

Because deploys preserve the `config/` folder, you do not need to recalibrate after every deploy. Recalibrate if you:

- Change the camera or lens.
- Change the focus or zoom.
- Switch to a resolution with no calibration entry.

## Next steps

- [Camera Calibration](../../getting-started/quick-start/camera-calibration.md)
- [Pipeline Settings](pipeline-settings.md)
- [Settings Page](settings-page.md)
- [Robot Pose](../../robot-interfacing/synapse-bridge/robot-pose.md)
