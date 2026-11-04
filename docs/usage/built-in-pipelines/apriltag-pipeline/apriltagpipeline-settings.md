---
description: >-
  Every setting exposed by the AprilTag pipeline, with defaults, effects, and
  tuning advice.
icon: gear-api
---

# ApriltagPipeline Settings

The AprilTag pipeline settings are grouped into **Target**, **Detection**, **Filtering**, and **Results** in the dashboard. Start with the defaults. Change one setting at a time and watch latency, detection rate, and pose stability.

## Target

### Tag Size

**Type:** Number\
**Default:** `0.1651 m` (6.5 in)\
**Range:** `0` and up

The physical width of one AprilTag in meters.

Measure the printed tag itself, not the white border or mounting material. This value must be the same for every tag the camera sees. An incorrect size makes distance and field-pose estimates wrong.

If you print your own tags, measure them with calipers. Printer scaling is a common source of error.

***

### Tag Family

**Type:** Enum\
**Options:** `tag36h11`, `tag16h5`\
**Default:** `tag36h11`

The tag encoding family the detector looks for.

The setting must match the physical tags. A `tag36h11` detector cannot read `tag16h5` tags. Official FRC field tags use `tag36h11`.

***

## Detection

These settings control the AprilTag detector itself. They come from WPILib's AprilTag implementation.

### Number of Threads

**Type:** Integer\
**Default:** `1`\
**Range:** `1` to the device's CPU thread count

The number of CPU threads used for detection.

More threads can reduce latency on multi-core devices, but they compete with camera capture, streaming, and other pipelines. Start with `1` or `2`, then increase only if detection latency is the bottleneck.

***

### Refine Edges

**Type:** Boolean\
**Default:** `False`

Refines tag corners after the initial detection.

Refinement can improve pose accuracy, especially with noisy or slightly blurred images. It also costs CPU time.

Enable it when accuracy matters more than frame rate.

***

### Quad Decimate

**Type:** Number\
**Default:** `1.0`\
**Range:** `1.0` and up

Downsamples the image before detection.

| Value | Effect |
| --- | --- |
| `1.0` | Full resolution, best accuracy and range |
| `2.0` | Half resolution, faster, shorter range |
| `3.0`+ | Much faster, but may miss small or distant tags |

This is the first setting to change when detection is too slow.

***

### Quad Sigma

**Type:** Number\
**Default:** `0.0`\
**Range:** `0.0` and up

Applies Gaussian blur before detection.

A small amount can reduce sensor noise. Too much blurs tag edges and reduces detection quality. Leave it at `0.0` unless you have a specific noise problem.

***

### Min Cluster Pixels

**Type:** Integer\
**Default:** `300`\
**Range:** `1` and up

Rejects candidate quads that contain too few pixels.

Raise it to ignore small, distant, or noisy candidates. Lower it if you need to detect very small tags, at the cost of more false candidates.

***

### Max Num Maxima

**Type:** Integer\
**Default:** `10`\
**Range:** `1` and up

The number of corner candidates considered when grouping pixels into a quad.

Higher values can help in cluttered scenes but cost processing time.

***

### Critical Angle

**Type:** Number\
**Default:** `45`\
**Range:** `0`–`90`

Controls rejection of quads whose edge pairs are nearly straight or nearly reversed. `0` disables this rejection.

{% hint style="warning" %}
WPILib expects this value in radians, but the pipeline currently forwards the configured value without converting degrees to radians. With the default `45`, the threshold is effectively very large and the rejection is mostly disabled. Leave it at the default unless you are testing this behavior. See [Known Issues](../../../additional-resources/known-issues.md).
{% endhint %}

***

### Max Line Fit MSE

**Type:** Number\
**Default:** `10`\
**Range:** `0` and up

The maximum mean squared error allowed when fitting lines to a contour.

Lower values reject non-quad shapes earlier, which saves processing time but may reject valid tags in blurry images. Raise it if tags are being missed.

***

### Min White Black Diff

**Type:** Integer\
**Default:** `5`\
**Range:** `0`–`255`

The minimum brightness difference between the white and black models of a tag.

Raise it in low-contrast or brightly lit scenes to reject false positives. Lower it if real tags are being missed.

***

### Deglitch

**Type:** Boolean\
**Default:** `False`

Removes small speckles from the thresholded image.

Only useful for very noisy images. It adds processing time.

***

## Filtering

### Crop X

**Type:** Range\
**Default:** `[-1, 1]`\
**Range:** `-1` to `1`

Limits the horizontal area the detector processes.

- `-1` is the left edge of the image.
- `1` is the right edge.

For example, `[-0.5, 0.5]` processes only the center half of the image. Cropping is one of the most effective ways to reduce latency when tags only appear in a known part of the frame.

The camera matrix is adjusted automatically for the crop.

***

### Crop Y

**Type:** Range\
**Default:** `[-1, 1]`\
**Range:** `-1` to `1`

Limits the vertical area the detector processes.

- `-1` is the top edge.
- `1` is the bottom edge.

Use it together with **Crop X** to focus on the region where tags appear.

***

## Results

### Stick To Ground

**Type:** Boolean\
**Default:** `False`

Constrains the estimated camera pose to the field ground plane by forcing its Z position to `0` and keeping only the yaw rotation.

This can reduce noise for a flat-field robot, but it makes the estimate wrong whenever the camera changes height or pitch. Do not enable it if the camera is tilted or mounted on a moving mechanism.

***

### Publish Camera Field Pose

**Type:** Boolean\
**Default:** `True`

Estimates and publishes the camera pose in field coordinates.

This is the main output of the pipeline and is required for robot localization. Keep it enabled.

{% hint style="warning" %}
The result serializer currently reads the camera pose unconditionally. Setting this to `False` while tags are visible can cause a serialization error. This setting is reserved for future use.
{% endhint %}

***

### Publish Tag Pose 3D

**Type:** Boolean\
**Default:** `False`

Reserved for publishing each tag's full 3D pose.

{% hint style="info" %}
This setting is defined but not currently used by the result serializer.
{% endhint %}

***

### Verbosity

**Type:** Enum\
**Default:** `kPoseOnly`

Reserved for controlling how much debug data is published per tag.

{% hint style="info" %}
This setting is defined but not currently used by the result serializer.
{% endhint %}

## Performance tuning

### If detection is too slow

1. Set **Crop X** and **Crop Y** to the region where tags appear.
2. Increase **Quad Decimate** to `1.5` or `2.0`.
3. Lower the camera resolution.
4. Increase **Number of Threads** to `2`.
5. Disable **Refine Edges**.

### If tags are missed

1. Set **Quad Decimate** back to `1.0`.
2. Increase camera resolution or move the camera closer.
3. Check focus and exposure.
4. Raise **Max Line Fit MSE**.
5. Lower **Min White Black Diff**.
6. Lower **Min Cluster Pixels**.

### If pose is inaccurate or jittery

1. Confirm the camera is calibrated at the active resolution.
2. Measure **Tag Size** with calipers.
3. Set **Quad Decimate** to `1.0`.
4. Enable **Refine Edges**.
5. Lock camera exposure and focus.
6. Make sure the field map poses are correct.

### If there are false detections

1. Raise **Min White Black Diff**.
2. Lower **Max Line Fit MSE**.
3. Confirm you are using the correct **Tag Family**.
4. Crop out areas with reflections or screens.
5. Improve lighting to reduce glare.

## Next steps

- [AprilTag Pipeline](README.md)
- [Camera Calibration](../../../getting-started/quick-start/camera-calibration.md)
- [How Synapse Works](../../../getting-started/how-synapse-works.md)
