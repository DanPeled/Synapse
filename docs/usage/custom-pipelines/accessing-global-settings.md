---
icon: earth-europe
---

# Accessing Global Settings

The Global Settings in Synapse store:

* Camera Config map&#x20;
* Camera Calibration data
* Camera details
* Camera to robot transform
* Default Pipeline indicies

Those values can be accessed via the `GlobalSettings` meta class, via methods such as `GlobalSettings.getCameraConfigMap()` which will result in a map between `CameraID` (int alias) and [`CameraConfig`](https://github.com/DanPeled/Synapse/blob/main/synapse_core/src/synapse/core/camera_factory.py#L106) .

Usage examples for this class can be seen in the [`ApriltagPipeline`](https://github.com/DanPeled/Synapse/blob/main/synapse_core/src/synapse/pipelines/apriltag_pipeline.py) class which uses it in order to gather the camera's distortion coeffs and instrict matrix.

