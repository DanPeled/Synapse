---
description: Improve AprilTag and pose accuracy by calibrating each camera at the resolution you use.
icon: camera-polaroid
---

# Camera Calibration

Camera calibration measures the camera's lens distortion and focal length. Synapse uses that information to turn a 2D image of an AprilTag into an accurate 3D pose.

{% hint style="warning" %}
Calibrate at the **same resolution** your pipeline uses. Calibration data is stored separately for each resolution, and using data from a different resolution will produce poor pose estimates.
{% endhint %}

You should calibrate even if you are not using AprilTags. Any pipeline that converts pixels to positions benefits from accurate distortion coefficients.

## What you need

- The camera mounted in its final position.
- A printed **Charuco** calibration board.
- A flat, rigid surface for the board. Tape it to a clipboard or piece of cardboard.
- Calipers to verify the printed dimensions.

## Print the calibration board

You can generate a board from the [Calib.io pattern generator](https://calib.io/pages/camera-calibration-pattern-generator) or another Charuco generator.

Synapse's calibration defaults are:

| Setting | Default |
| --- | --- |
| Board type | Charuco |
| Dictionary | `DICT_5X5_1000` |
| Squares X | `5` |
| Squares Y | `7` |
| Square length | `0.04 m` (40 mm) |
| Marker length | `0.02 m` (20 mm) |
| Images to capture | `20` |

Print at **100% scale** (do not let the printer "fit to page"), then measure a square and a marker with calipers. If the printed size differs from the configured values, either reprint or change the settings in the calibration dialog to match reality.

{% hint style="info" %}
The board size, square length, marker length, and dictionary are all editable in the calibration dialog. If you use a different board, update these values before capturing images.
{% endhint %}

## Calibrate in the web UI

1. Open the dashboard at `http://<device-ip>:3000`.
2. Go to the **Camera** page.
3. Select the camera.
4. Choose the resolution you will use for vision.
5. Press **Calibrate**.
6. In the calibration dialog, confirm the board settings match your printed board.
7. Hold the board in front of the camera.

A green check mark appears in the camera view when Synapse sees enough Charuco corners. Only capture an image when the check mark is visible.

8. Capture images from many different positions and angles.

{% hint style="success" %}
Aim for at least 20 good images. More images from varied angles generally produce better results. You can raise **Images to Capture** if you want more.
{% endhint %}

## Tips for good calibration

- **Move the board, not the camera.** The camera should stay exactly where it will be on the robot.
- **Tilt the board.** Capture images at angles up to about 45°. Avoid only straight-on shots.
- **Cover the whole frame.** Put the board near each corner and the center.
- **Fill a reasonable part of the image.** Very small boards give noisy corner detection.
- **Keep the board flat.** A warped board adds error that calibration cannot remove.
- **Avoid motion blur.** Hold still while capturing.
- **Keep lighting even.** Avoid glare and harsh shadows.
- **Do not change focus or zoom** between calibration and competition. If you do, recalibrate.

## Reading the results

After calibration, Synapse stores:

- The **camera matrix** (focal length and principal point).
- The **distortion coefficients**.
- The **mean reprojection error**.

Lower reprojection error is better. As a rough guide:

| Mean error | Quality |
| --- | --- |
| `< 0.5` | Excellent |
| `0.5 – 1.0` | Good |
| `1.0 – 2.0` | Usable, but improves with more/better images |
| `> 2.0` | Recalibrate |

The Camera page shows these values for each calibrated resolution and lets you delete a calibration.

## Import calibration from another tool

If you calibrated the camera elsewhere, you can import the result instead of recalibrating:

1. Export the calibration as JSON from a tool such as [CalibDB](https://calibdb.net/) or WPIcal.
2. On the Camera page, press **Import Results**.
3. Select the JSON file.

Synapse accepts the standard OpenCV-style calibration shape used by CalibDB and the flat format used by WPIcal. Imported data is applied to the camera and stored in the project config.

{% hint style="info" %}
Imported calibration is matched to the camera index and resolution in the file. If the import does not apply, check that the resolution in the file matches a resolution the camera supports.
{% endhint %}

## Calibration and the project config

Calibration data is stored on the coprocessor in:

```text
config/camera_<index>/camera_configs.yml
```

Each resolution has its own entry with `matrix`, `distCoeffs`, `measured_res`, and `mean_err`.

Because deploy preserves the `config/` folder, you do not need to recalibrate after every code deploy. You do need to recalibrate if you:

- Change the camera.
- Change the camera's focus or lens.
- Move the camera mounting in a way that changes the lens (rare).
- Switch to a resolution that has no calibration entry.

## Next steps

- [Apriltag Pipeline](../../usage/built-in-pipelines/apriltag-pipeline/README.md)
- [Camera Page](../../usage/built-in-pipelines-1/camera-page.md)
- [Robot Pose](../../robot-interfacing/synapse-bridge/robot-pose.md)
