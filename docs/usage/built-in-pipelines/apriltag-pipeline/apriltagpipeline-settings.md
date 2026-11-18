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

These settings control the **NAPA** AprilTag detector (`napa-vision==0.5.1`). NAPA performs detection only; pose estimation is handled separately by the pipeline's OpenCV `solvePnPGeneric` step. Changing `tag_family` or any of these detection settings rebuilds the native detector, so avoid toggling them repeatedly while the pipeline is running.

### Min Tag Px

**Type:** Integer\
**Default:** `32`\
**Range:** `8`–`30000`, step `1`

Smallest tag side, in pixels, that is guaranteed to be sampled.

Lower values find smaller or more distant tags, but cost more CPU time. Raise it when detection is too slow; lower it when distant tags are missed.

***

### Max Hamming

**Type:** Integer\
**Default:** `-1`\
**Range:** `-1`–`3`, step `1`

Number of payload bits that may be corrected when decoding a tag.

`-1` uses the selected tag family's default. Values `0`–`3` allow progressively more bit errors, which can recover distorted tags but also increases the chance of false positives.

***

### Min Contrast

**Type:** Integer\
**Default:** `20`\
**Range:** `1`–`255`, step `1`

Minimum grey-level difference between the tag and its white margin.

Raise it in low-contrast or brightly lit scenes to reject false positives. Lower it if real tags are being missed.

***

### Min Border Cells

**Type:** Integer\
**Default:** `22`\
**Range:** `0`–`28`, step `1`

Number of border cells that must read dark before a candidate is decoded, scaled for the selected family.

Raise it to reject weaker candidates. Lower it if tags with damaged or poorly lit borders are being missed.

***

### Sharpening

**Type:** Number\
**Default:** `0.25`\
**Range:** `0.0`–`1.0`

Cell sharpening applied before decoding.

A small amount can improve decoding on soft images. Too much can amplify sensor noise. Leave it near the default unless you have a specific contrast problem.

***

### Max Detections

**Type:** Integer\
**Default:** `64`\
**Range:** `1` and up, step `1`

Maximum number of tags returned per frame.

Reduce it when you only expect a few tags and need to save processing time. Raise it if many tags are in view and some are being dropped.

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

{% hint style="warning" %}
The camera matrix is not currently adjusted for the crop. Detections are measured in the cropped image, but the pose solver still uses the full-frame principal point, so a tight crop can make the published camera pose less accurate. Keep the crop generous, or leave it at `[-1, 1]` when you rely on field localization. See [Known Issues](../../../additional-resources/known-issues.md#cropping-shifts-the-apriltag-pose).
{% endhint %}

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

### Tag Filter

**Type:** Integer list\
**Default:** `[]` (empty)

Only report detections for these tag IDs. Leave the list empty to target every tag.

The dashboard renders a comma-separated integer editor, for example `1, 2, 7`. Non-empty filters are applied immediately after detection, before markers are drawn, results are published, and the camera pose is estimated. Filtered-out tags therefore do not appear in `tags` and do not contribute to the camera pose.

A filter with IDs that are not present in the field map still produces no result for those tags. Keep the list empty when you want the pipeline to use every tag it can see.

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

This is the main output of the pipeline and is required for robot localization. Keep it enabled when you need a field pose.

When this is `False`, the pipeline skips pose estimation entirely. The result still contains the filtered `tags`, but `cameraEstimate_fieldSpace` is `null` (`None` in Python) and `reprojection_error` is `0.0`. It no longer causes a serialization error.

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
**Options:** `kPoseOnly` (`0`), `kTagDetails` (`1`), `kTagDetectionData` (`2`), `kAll` (`3`)\
**Default:** `kPoseOnly` (`0`)

Reserved for controlling how much debug data is published per tag. The helper that maps verbosity levels to ignored result keys exists, but it is not called by the current serializer.

{% hint style="info" %}
This setting is defined but not currently used. Changing it has no effect on published results.
{% endhint %}

## Config migration

The switch from the WPILib detector to NAPA changed the detection settings. Old saved configs are accepted, but some keys are ignored and others are renamed automatically.

**Retired keys (ignored when loading old configs):**

- `detector_type`
- `num_threads`
- `refine_edges`
- `quad_decimate`
- `quad_sigma`
- `min_cluster_pixels`
- `max_num_maxima`
- `critical_angle`
- `max_line_fit_mse`
- `min_white_black_diff`
- `deglitch`

**Renamed keys:**

| Old key | Current key |
| --- | --- |
| `napa_min_tag_px` | `min_tag_px` |
| `napa_max_hamming` | `max_hamming` |
| `napa_min_contrast` | `min_contrast` |
| `napa_min_border_cells` | `min_border_cells` |
| `napa_sharpening` | `sharpening` |
| `napa_max_detections` | `max_detections` |

A renamed key is only applied when the current key is absent. If both are present, the current key wins. After upgrading, press **Save** in the dashboard to write the migrated settings back to disk.

{% hint style="info" %}
Example projects in the repository may still contain retired WPILib keys. They do not affect the running pipeline; use the current keys listed above when tuning detection.
{% endhint %}

## Performance tuning

### If detection is too slow

1. Set **Crop X** and **Crop Y** to the region where tags appear.
2. Raise **Min Tag Px** (for example, `48` or `64`).
3. Reduce **Max Detections** if you only expect a few tags.
4. Lower the camera resolution.
5. Raise **Min Contrast** or **Min Border Cells** slightly to reject weak candidates earlier.
6. Avoid changing **Tag Family** or detection settings every frame; each change rebuilds the native detector.

### If tags are missed

1. Lower **Min Tag Px**.
2. Lower **Min Contrast** and **Min Border Cells**.
3. Check **Max Hamming**; `-1` uses the family default, and `2` or `3` tolerates more distorted tags.
4. Confirm **Tag Filter** is empty or contains the IDs you expect.
5. Increase camera resolution or move the camera closer.
6. Check focus, lighting, and **Tag Family**.
7. Raise **Max Detections** if many tags are in view.

### If pose is inaccurate or jittery

1. Confirm the camera is calibrated at the active resolution.
2. Measure **Tag Size** with calipers.
3. Use multiple tags where possible and check `reprojection_error`.
4. Lock camera exposure and focus.
5. Make sure the field map poses are correct.
6. Keep **Publish Camera Field Pose** enabled; with it disabled, no pose is produced.
7. Only use **Stick To Ground** when the camera really is level at a fixed height.

### If there are false detections

1. Raise **Min Contrast**.
2. Raise **Min Border Cells**.
3. Lower **Sharpening** if noisy images are being over-sharpened.
4. Use **Tag Filter** to allow only the IDs you expect.
5. Confirm you are using the correct **Tag Family**.
6. Crop out areas with reflections or screens and improve lighting to reduce glare.

## Next steps

- [AprilTag Pipeline](README.md)
- [Camera Calibration](../../../getting-started/quick-start/camera-calibration.md)
- [How Synapse Works](../../../getting-started/how-synapse-works.md)
