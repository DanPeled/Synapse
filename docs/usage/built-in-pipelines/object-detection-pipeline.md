---
description: Detect objects with any Ultralytics-compatible model and estimate approximate field positions.
icon: scan-search
---

# Object Detection Pipeline

The object detection pipeline runs an Ultralytics-compatible detection model on every camera frame. It works with any model that exposes class names, so it is not limited to a fixed set of game pieces. If you provide approximate physical sizes, it can also estimate each object's distance and field position.

The pipeline class is `YOLOPipeline`. Its settings class is `YOLOSettings`, and its result class is `NeuralResult`.

Use it for:

- Detecting game pieces with a trained model.
- Detecting several classes in one frame.
- Getting approximate distance and field coordinates for each detection.
- Drawing labeled boxes on the camera feed.

For simple color-based targets, the [Color Detection Pipeline](color-detection-pipeline.md) is easier. For fiducial-based localization, use the [Apriltag Pipeline](apriltag-pipeline/README.md).

## Install the optional dependencies

PyTorch and Ultralytics are large dependencies, so they are not installed with Synapse by default. Install them on the coprocessor:

```bash
pip install "synapsefrc[yolo]"
```

This installs `torch>=2.1` and `ultralytics>=8.0.200`.

{% hint style="warning" %}
The pipeline is only registered when both dependencies can be imported when the runtime starts. If you install them while Synapse is already running, restart the runtime before looking for `YOLOPipeline` in the dashboard.
{% endhint %}

## Add the pipeline

1. Open the dashboard.
2. Select a camera.
3. Press **Add Pipeline**.
4. Choose **YOLOPipeline**.
5. Give it a name, such as **Object Detection**, and press **Add Pipeline**.
6. Select it from the pipeline dropdown.
7. Press **Save** when you are happy with the settings.

The example project also contains a commented-out pipeline slot you can uncomment. A minimal version of that slot looks like this:

```yaml
3:
  name: Object Detection
  type: YOLOPipeline
  settings:
    model_file: config/models/coralAlgae-640-640-yolov8s.pt
    object_dimensions_file: config/models/object_dimensions.example.json
```

## Model files

The `model_file` setting accepts Ultralytics-compatible models with these extensions:

- `.pt`
- `.onnx`
- `.engine`

The default is `config/models/coralAlgae-640-640-yolov8s.pt`. The example project includes that model and an example dimensions file in `config/models/`.

Paths are relative to the Synapse project root. On the coprocessor, put models in:

```text
~/Synapse/config/models/
```

You can also upload a model with the file picker in the pipeline settings. The picker starts in `config/models` and filters for the supported extensions. The file must exist, be a regular file, and be inside the project directory.

{% hint style="info" %}
A deploy preserves the existing `config/` folder on the coprocessor. Upload models through the dashboard or copy them into `~/Synapse/config/models/` directly; do not assume that files placed in a local `config/` folder are uploaded on the next deploy.
{% endhint %}

The pipeline loads the model when it starts and reloads it when `model_file` changes to a different path. Saving the same path again does not reload the model. It tries Ultralytics' `YOLO` loader first and falls back to `RTDETR` when needed. Inference uses CUDA when PyTorch reports that it is available; otherwise it uses the CPU. If the model cannot be loaded, the camera stream keeps running and the result contains an `error` message.

## Settings

Numeric settings with a maximum render as a slider; settings without a maximum render as a number input. Sliders snap to the configured step. Camera properties such as `resolution` and `exposure` appear in their own category as usual.

### Model

| Key | Type / constraint | Default | Description |
| --- | --- | --- | --- |
| `model_file` | File picker, `config/models`, files `.pt`/`.onnx`/`.engine` | `config/models/coralAlgae-640-640-yolov8s.pt` | Model to load. Changing it to a different path reloads the model. |
| `confidence_threshold` | Number, `0.0`–`1.0`, step `0.01` | `0.3` | Minimum detection confidence passed to the model. |
| `iou_threshold` | Number, `0.0`–`1.0`, step `0.01` | `0.45` | Non-maximum suppression IoU threshold passed to the model. |

### Object Size

| Key | Type / constraint | Default | Description |
| --- | --- | --- | --- |
| `object_dimensions_file` | File picker, `config/models`, files `.json` | empty | Optional JSON file mapping class names to physical sizes in meters. |
| `default_object_width` | Number, minimum `0.0`, step `0.01` | `0.3` meters | Width used for classes without an explicit entry. |
| `default_object_height` | Number, minimum `0.0`, step `0.01` | `0.3` meters | Height used for classes without an explicit entry. |

### Filtering

| Key | Type / constraint | Default | Description |
| --- | --- | --- | --- |
| `min_bbox_area` | Number, minimum `0.0`, step `1.0` | `100.0` px² | Ignore detections with a smaller bounding-box area. |
| `min_distance` | Number, minimum `0.0`, step `0.1` | `0.1` meters | Reject position estimates closer than this. |
| `max_distance` | Number, minimum `0.0`, step `0.1` | `50.0` meters | Reject position estimates farther than this. |
| `max_reprojection_error` | Number, minimum `0.0`, step `1.0` | `50.0` pixels | Reject estimates whose reprojection error is larger than this. |

### Display

| Key | Type / constraint | Default | Description |
| --- | --- | --- | --- |
| `draw_detections` | Boolean | `true` | Draw boxes and labels on the camera feed. Green is high confidence, yellow is medium, and orange is low. |
| `debug_logging` | Boolean | `false` | Log detection counts and inference time. |

### Camera Pose

These values tell the pipeline where the camera is on the field. They are used to rotate the camera-space estimate into field coordinates. The pipeline does not read them from a field map.

| Key | Type / constraint | Default | Description |
| --- | --- | --- | --- |
| `camera_x` | Number, no bound | `0.0` meters | Camera X position on the field. |
| `camera_y` | Number, no bound | `0.0` meters | Camera Y position on the field. |
| `camera_z` | Number, no bound | `1.0` meters | Camera height above the field. |
| `camera_roll` | Number, `-180.0`–`180.0`, step `1.0` | `0.0` degrees | Camera roll. |
| `camera_pitch` | Number, `-180.0`–`180.0`, step `1.0` | `0.0` degrees | Camera pitch; positive tilts down. |
| `camera_yaw` | Number, `-180.0`–`180.0`, step `1.0` | `0.0` degrees | Camera yaw; counter-clockwise from +X. |

## Object dimensions JSON

Position estimation needs an approximate physical width and height for each class. Classes without an entry use `default_object_width` and `default_object_height` (both `0.3` meters by default).

Set `object_dimensions_file` to a JSON file in `config/models/`. Class names must match the names reported by your model exactly, including spaces and capitalization:

```json
{
  "coral": {"width": 0.30, "height": 0.30},
  "algae": {"width": 0.30, "height": 0.30},
  "person": {"width": 0.45, "height": 1.70},
  "sports ball": [0.22, 0.22]
}
```

Each value can be either:

- An object with `width` and `height` fields, in meters.
- A two-item array: `[width, height]`, in meters.

Widths and heights must be positive, finite numbers. Invalid entries are ignored and reported in the log, so one bad class does not discard the whole file. The example above is available at `config/models/object_dimensions.example.json` in the example project.

## How 3D estimation works

For each detection, the pipeline:

1. Passes the frame to the model with the configured confidence and IoU thresholds.
2. Reads the model's bounding boxes, confidences, and class IDs.
3. Drops boxes smaller than `min_bbox_area`.
4. Uses the bounding box and the class's approximate width/height to solve a planar PnP problem.
5. Uses camera calibration to convert the result into a camera-space vector.
6. Rotates and translates that vector using `camera_x/y/z/roll/pitch/yaw` into field coordinates.
7. Draws the box and publishes the result.

This is an **approximate** estimate, not a precise pose solution like AprilTag localization. Accurate calibration at the resolution you actually use is important. If calibration is missing, the pipeline uses an identity camera matrix and zero distortion, which will give poor estimates. The camera is not the robot: to get a robot pose you still need to apply your robot-to-camera transform in robot code.

See [Camera Calibration](../../getting-started/quick-start/camera-calibration.md) before relying on distance or field coordinates.

## Results

The pipeline publishes final results to `<camera>/data/results` as MessagePack-encoded `raw` data. See the [NetworkTables API](../../additional-resources/networktables-api.md) for the table layout and decoding options.

The decoded top-level result is:

| Key | Type | Description |
| --- | --- | --- |
| `detections` | array | One entry per published detection. Empty when nothing is detected or the model failed. |
| `model` | string | Filename of the loaded model, or empty when no model is loaded. |
| `error` | string | Empty on success; otherwise an explanation such as a missing model file or failed inference. |

Each `detections[]` entry contains:

| Key | Type | Description |
| --- | --- | --- |
| `className` | string | Class name from the model. |
| `x` | float | Bounding-box center X in pixels. |
| `y` | float | Bounding-box center Y in pixels. |
| `confidence` | float | Detection confidence from the model. |
| `bbox` | `[x1, y1, x2, y2]` | Bounding box corners in pixels; origin is the top-left. |
| `position3D` | object or null | Estimated field position, or `null` when the estimate was rejected. |

Each non-null `position3D` contains:

| Key | Type | Description |
| --- | --- | --- |
| `fieldX` | float | Estimated X coordinate on the field, in meters. |
| `fieldY` | float | Estimated Y coordinate on the field, in meters. |
| `fieldZ` | float | Estimated Z coordinate on the field, in meters. |
| `distance` | float | Distance from the camera, in meters. |
| `qualityScore` | float | Heuristic score combining confidence, box area, distance, and reprojection error. |
| `reprojectionError` | float | Mean reprojection error in pixels; lower is better. |
| `bboxArea` | float | Bounding-box area in pixels squared. |
| `cameraFrame` | `{x, y, z}` | Position in the camera's optical frame. |
| `objectWidth` | float | Width used for this class, in meters. |
| `objectHeight` | float | Height used for this class, in meters. |

{% hint style="info" %}
The pipeline does not publish an auxiliary `hasResults` key. Read `data/results` and check whether `detections` is empty and whether `error` is set.
{% endhint %}

Boxes smaller than `min_bbox_area` are discarded before a detection is created, so they are not published. A published detection still has `position3D` set to `null` when its configured width or height is not positive, the PnP solve fails, the reprojection error exceeds `max_reprojection_error`, or the estimated distance falls outside `min_distance`–`max_distance`. The detection itself is still reported in those cases.

## Limitations

- The optional dependencies are large, and the pipeline is hidden from the dashboard until they are installed and the runtime is restarted.
- A failed inference drops the model. It will not run again until `model_file` changes to a different path or the runtime restarts; the result's `error` field explains the failure.
- Position estimates depend on the assumed object size. Wrong dimensions produce wrong distances even when the bounding box is correct.
- Two objects of the same class are distinguished only by their separate detections; there is no tracking.
- The pipeline does not provide a typed SynapseLib result class. Use the raw NetworkTables result or define a custom result type with type string `YOLOPipeline`.
- For fully custom models, preprocessing, or post-processing, write a [Custom Pipeline](../custom-pipelines/README.md).

## Next steps

- [Built In Pipelines](README.md)
- [Color Detection Pipeline](color-detection-pipeline.md)
- [Apriltag Pipeline](apriltag-pipeline/README.md)
- [Custom Pipelines](../custom-pipelines/README.md)
- [Camera Calibration](../../getting-started/quick-start/camera-calibration.md)
- [NetworkTables API](../../additional-resources/networktables-api.md)
