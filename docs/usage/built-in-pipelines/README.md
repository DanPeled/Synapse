---
description: Pipelines that ship with Synapse and are ready to use.
icon: pipe-section
---

# Built In Pipelines

Synapse includes several pipelines that work without writing any vision code. Add one to a camera from the dashboard and tune it with the generated settings.

## AprilTag pipeline

Detects AprilTags and estimates the camera's pose relative to the field.

- **Class:** `ApriltagPipeline`
- **Use it for:** robot localization, aiming at field elements, pose estimation, distance to a tag.
- **Needs:** camera calibration, a field map (`deploy/fmap.json`), and correct tag size.

[AprilTag Pipeline](apriltag-pipeline/README.md)

## Color pipeline

Finds objects in a configurable HSV color range.

- **Class:** `ColorPipeline`
- **Use it for:** game-piece detection, line following, aiming at a colored target.
- **Needs:** a color range tuned for your lighting.

[Color Detection Pipeline](color-detection-pipeline.md)

## Calibration pipeline

Used internally when you press **Calibrate** on the Camera page.

- **Class:** `CalibrationPipeline`
- **Visible in the UI as:** a system pipeline (`$$CalibrationPipeline$$`).
- **Do not add this manually.** The calibration screen adds and removes it automatically.

## System pipelines

System pipelines are marked with a type wrapped in `$$`, for example `$$CalibrationPipeline$$`. The dashboard hides them from the normal **Add Pipeline** list and manages them itself.

## Which pipeline should I use?

| Goal | Pipeline |
| --- | --- |
| Know where the robot is on the field | AprilTag |
| Aim at a specific tag | AprilTag |
| Detect a colored game piece | Color |
| Detect an object with a custom model | [Custom pipeline](../custom-pipelines/README.md) |
| Calibrate the camera | Calibration (built into the UI) |

## Next steps

- [AprilTag Pipeline](apriltag-pipeline/README.md)
- [Color Detection Pipeline](color-detection-pipeline.md)
- [Custom Pipelines](../custom-pipelines/README.md)
- [Pipeline Settings](../built-in-pipelines-1/pipeline-settings.md)
