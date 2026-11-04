---
description: Tour of the Synapse web dashboard, camera page, and settings page.
icon: browsers
layout:
  width: default
  title:
    visible: true
  description:
    visible: true
  tableOfContents:
    visible: true
  outline:
    visible: true
  pagination:
    visible: true
  metadata:
    visible: true
---

# UI Interaction

The Synapse web UI runs on the coprocessor and is available from any browser on the same network:

```text
http://<device-ip>:3000
```

No installation is needed. The runtime serves the UI, the camera streams, and the WebSocket connection that keeps settings and results live.

## Pages

Use the sidebar to switch between pages:

| Page | What it is for |
| --- | --- |
| **Dashboard** | Live camera view, pipeline selection, settings, and results |
| **Camera** | Camera information, calibration, and import/export |
| **Settings** | Device info, network settings, logs, and maintenance |

## Dashboard

The dashboard is the page you will use most.

- **Camera view** shows the selected camera's processed stream and current FPS/latency.
- **Camera selector** switches between cameras.
- **Pipeline selector** switches the active pipeline for the selected camera.
- **Pipeline actions** menu contains Rename, Add Pipeline, Set As Default, Duplicate, Change Type, and Delete.
- **Save** writes the current settings to disk on the device.
- **Lock** prevents accidental setting changes.
- **Record** saves the camera stream to an MP4 file on the device.
- **Settings tabs** are generated from the pipeline's setting categories.
- **Results** shows the latest auxiliary values and decoded pipeline results.

### Switching pipelines

1. Select a camera.
2. Open the **Pipeline** dropdown.
3. Choose the pipeline you want.

The change takes effect immediately. The default pipeline is marked with a star and is used when the runtime starts or when robot code selects the default index.

### Adding a pipeline

1. Open the pipeline actions menu.
2. Choose **Add Pipeline**.
3. Enter a name.
4. Choose a pipeline type.
5. Press **Add Pipeline**.

The new pipeline starts with default settings. Use **Duplicate** to copy an existing pipeline and its tuned values.

### Saving, locking, and recording

- Settings changed in the UI are applied immediately but only persisted when you press **Save**.
- **Lock** makes the controls read-only. It does not stop the pipeline.
- **Record** starts or stops writing the camera stream to `records/` on the device. Check free storage before recording for a long time.

## Camera page

The Camera page shows the camera configuration and calibration tools.

- Camera selector.
- Camera index, device UID, stream path, default pipeline, and max FPS.
- Rename action.
- Calibration for each resolution.
- **Calibrate** and **Import Results** buttons.

The **Remove Camera** action is currently disabled.

See [Camera Page](camera-page.md).

## Settings page

The Settings page contains:

- Device info and hardware metrics.
- Network settings.
- Import/export settings.
- Logs.
- Restart and factory reset actions.

See [Settings Page](settings-page.md).

## Results panel

The results panel decodes the latest pipeline result and lists auxiliary values. You can copy values to the clipboard, which is useful when tuning thresholds or checking a pose.

- **MessagePack results** are shown as an expandable tree.
- **Primitive values** are shown in a table.

If the panel is empty, the current pipeline may not have produced a result yet, or no tags/objects were detected.

## Tips

- Use the same browser window for tuning and robot code testing.
- If the camera stream does not load, refresh the page. See [Known Issues](../../additional-resources/known-issues.md).
- Latency shown in the UI is processing latency in milliseconds. NetworkTables publishes latency values in seconds.
- Changes that affect network settings require a runtime restart.

## Next steps

- [Pipeline Settings](pipeline-settings.md)
- [Camera Page](camera-page.md)
- [Settings Page](settings-page.md)
- [Built In Pipelines](../built-in-pipelines/README.md)
