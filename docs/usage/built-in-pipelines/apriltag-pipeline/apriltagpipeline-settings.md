---
description: >-
  The AprilTag pipeline provides settings for controlling detection accuracy,
  performance, filtering, and output data.
icon: gear-api
---

# ApriltagPipeline Settings

## Detector settings

These settings control AprilTag detection and pose estimation. Start with the defaults. Change one setting at a time while monitoring latency and pose stability.

### Tag Size

**Type:** Number\
**Default:** `0.1651 m` (6.5 in)

The physical width of one AprilTag, in meters.

Measure the printed tag itself. Do not include its white border or mounting material. This value must match every tag that the camera detects. An incorrect size causes incorrect distance and field-pose estimates.

***

### Tag Family

**Type:** Enum\
**Options:**

* `tag36h11`
* `tag16h5`

**Default:** `tag36h11`

The tag encoding family to detect.

This must match the physical tags. A detector cannot identify tags from another family. Use `tag36h11` for the official FRC field layout.

***

### Number of Threads

**Type:** Integer\
**Default:** `1`

The CPU threads available to the detector.

More threads can reduce detection latency. They also leave fewer resources for other cameras and pipelines. The best value depends on the coprocessor, camera resolution, and active workloads.

{% hint style="info" icon="thumbs-up" %}
* Start with `1-2` threads.
* Increase it only if latency remains high.
* Reserve CPU capacity for other vision tasks.
{% endhint %}

***

### Refine Edges

**Type:** Boolean\
**Default:** `False`

Enables extra corner refinement after tag detection.

Refined corners can improve pose estimates. They also increase processing time.

{% hint style="info" icon="thumbs-up" %}
Enable this when pose accuracy matters more than latency. Disable it for higher frame rates.
{% endhint %}

***

### Quad Decimate

**Type:** Number\
**Default:** `1.0`

Controls how much the detector downsamples the image.

A higher value uses a smaller image. This lowers CPU use and latency. It also reduces detection range and corner accuracy.

Examples:

* `1.0` — full resolution and best accuracy.
* `2.0` — half resolution and faster detection.
* Higher values — lower latency with less range.

***

### Quad Sigma

**Type:** Number\
**Default:** `0.0`

Applies Gaussian blur before detection.

Small values can reduce image noise. Large values blur tag edges and reduce detection quality.

{% hint style="info" icon="thumbs-up" %}
Keep this at `0.0` unless image noise causes repeatable detection failures.
{% endhint %}

***

### Iteration Count

**Type:** Integer\
**Default:** `4`

The pose-estimation refinement iterations.

Higher values may improve pose accuracy. They increase processing time.

***

## Filtering

### Crop X

**Type:** Range\
**Default:** `[-1, 1]`

Limits the horizontal image area that the detector processes.

The range is normalized:

* `-1` is the left edge.
* `1` is the right edge.

For example, `[-0.5, 0.5]` processes the center half of the image.

Crop the image when tags only appear in a known region. Cropping can substantially reduce latency.

***

### Crop Y

**Type:** Range\
**Default:** `[-1, 1]`

Limits the vertical image area that the detector processes.

The range is normalized:

* `-1` is the top edge.
* `1` is the bottom edge.

Use this with **Crop X** to limit detection to the expected tag area.

***

## Results

### Stick To Ground

**Type:** Boolean\
**Default:** `False`

Constrains the estimated camera pose to the field ground plane.

This can reduce noise for a robot that remains on a flat field. Do not enable it when the camera changes height or pitch significantly.

***

### Publish Camera Field Pose

**Type:** Boolean\
**Default:** `True`

Publishes the estimated camera pose in field coordinates.

This requires:

* A configured field AprilTag layout.
* Valid AprilTag detections.

Use this output with robot-localization systems, such as WPILib pose estimators.

***

### Publish Tag Pose 3D

**Type:** Boolean\
**Default:** `False`

Publishes the full 3D pose of each detected AprilTag.

Each pose includes position, rotation, and camera distance. Enable this for debugging or applications that use individual tag poses. Disable it when only camera field pose is needed.

***

### Verbosity

**Type:** Enum\
**Default:** `kPoseOnly`

Controls pipeline logging and debug output.

{% hint style="info" icon="thumbs-up" %}
Use `kPoseOnly` during normal competition operation. Use higher levels when debugging detection or calibration.
{% endhint %}

Higher verbosity can increase logging overhead.

***

## Performance Tuning

### Reducing Latency

If AprilTag detection is too slow, make these changes in order:

1. Crop the image with **Crop X** and **Crop Y**.
2. Increase **Quad Decimate**.
3. Reduce camera resolution.
4. Increase **Number of Threads**.
5. Disable **Refine Edges**.

### Improving Accuracy

If pose estimates are inaccurate, check these items:

1. Verify camera calibration at the selected resolution.
2. Measure the physical tag size and verify **Tag Size**.
3. Set **Quad Decimate** to `1.0`.
4. Enable **Refine Edges**.
5. Increase **Iteration Count** if latency allows.
6. Ensure each tag is flat and securely mounted.
