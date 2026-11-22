# Multi-camera performance target: OV9782

## Goal

Run four OV9782 cameras simultaneously at their maximum UVC resolution while each
camera sustains at least **83% of the maximum single-camera throughput** measured
with the same pipeline. Higher throughput is always better; 83% is a floor, not a
ceiling.

The primary metrics are:

- **Per-camera processed FPS**: successful pipeline results per second, measured
  independently for each camera.
- **Aggregate processed FPS**: the sum of the four per-camera rates.
- **Capture-to-result latency**: P50/P95/P99 from the frame's capture timestamp to
  the completed result becoming available to consumers.
- **Frame freshness**: how many frames were captured but never processed, and the
  age of the newest result.
- **Host cost**: CPU utilization and peak RSS during a sustained run.

The pass condition is:

```text
min(FPS_1, FPS_2, FPS_3, FPS_4) >= 0.83 * baseline_single_camera_fps
```

## Why 1280x720 MJPEG is the benchmark mode

The OV9782 itself is a 1/4-inch global-shutter sensor capable of 1280x800 at 120
FPS over 2-lane MIPI or DVP, and it lists 1280x720 as a supported image size
([OmniVision](https://www.ovt.com/products/ov9782/)). The USB UVC modules used in
FRC vision setups advertise 1280x720 at 120 FPS in **MJPG only** over USB 2.0;
they explicitly warn that YUY2 does not reach that frame rate
([CM Technology CMT-1MP-OV9782-R352](http://www.camera-module.com/product/others/color-global-shutter-camera-module-120fps-ov9782.html)).

Therefore the benchmark uses 1280x720 MJPEG as the maximum practical UVC mode.

## USB bandwidth envelope

USB 2.0 High Speed has a 480 Mbit/s signaling rate and a maximum theoretical data
throughput of about 53 MB/s per bus
([USB overview](https://en.wikipedia.org/wiki/USB#USB_2.0)). All devices behind
the same host controller share that budget, and real payload throughput is lower
after protocol overhead.

If one camera reaches the advertised 120 FPS, the 83% target is 99.6 FPS per
camera, or 398.4 FPS aggregate. The average compressed frame size that fits on
one USB 2.0 bus is therefore:

```text
max_bytes_per_frame = bus_bytes_per_second / (4 * target_fps_per_camera)
```

Using the theoretical 53 MB/s ceiling gives about 133 kB/frame. Using a more
realistic 35-40 MB/s payload budget gives roughly 88-100 kB/frame. If the scene
makes the camera emit larger MJPEG frames, four cameras cannot all reach the
target on a single shared USB 2.0 bus regardless of application optimizations.

Uncompressed video is not viable: four 1280x720 YUY2 streams at 120 FPS would
need about 884 MB/s before protocol overhead. MJPEG compression is mandatory for
this target.

Some UVC cameras also over-report the bandwidth they require, causing Linux's
UVC driver to reject additional cameras on the same bus
([Arducam forum report](https://forum.arducam.com/t/linux-uvc-driver-bandwidth-issues/6731)).
The benchmark must record the host-controller/bus topology; four cameras on four
independent buses are a materially different test from four cameras behind one
hub.

## What software can and cannot fix

Software can remove application-side serialization: per-camera capture, decode,
processing, and publication should not wait on a single global worker or on
socket/NetworkTables I/O. Software cannot increase the shared USB 2.0 payload
budget. If the bus is saturated, the honest outcomes are to report the measured
shortfall or reduce resolution/frame rate; they are not to hide dropped frames.

The multi-camera work therefore targets:

1. one independent capture/processing lane per camera;
2. newest-frame selection with bounded queues instead of unbounded stale frames;
3. no global locks or single worker in the per-frame path;
4. off-loop publication for results, streams, and diagnostics; and
5. a runnable benchmark that reports whether the limit is host CPU, application
   serialization, or USB bandwidth.

## Benchmark protocol

1. Warm up all cameras and the pipeline for at least 10 seconds.
2. Measure a single camera at 1280x720 MJPEG for 60 seconds; record achieved
   processed FPS and latency percentiles as the baseline.
3. Measure four cameras at the same settings for 60 seconds.
4. Record per-camera processed FPS, capture FPS, dropped/stale frames, MJPEG
   bytes per frame, latency percentiles, CPU, and peak RSS.
5. Record USB topology (`lsusb -t` on Linux, or equivalent platform information).
6. Pass only when every camera meets `0.83 * baseline`; otherwise report the
   bottleneck and the measured per-camera ratios.

This protocol makes the claim falsifiable on the target robot hardware without
requiring four OV9782 cameras on the development machine.

## Running the benchmark

The benchmark starts a headless runtime from a Synapse project and reports JSON.
Use one project config containing only the camera under test for the baseline,
then a config containing all four cameras for the comparison.

```bash
# 1. Single-camera baseline, using the project's 1280x720 MJPEG settings.
python scripts/benchmark_multi_camera.py \
  --project /path/to/single-camera-project \
  --warmup 10 --duration 60 \
  --output baseline.json

# 2. Four-camera run, checked against that baseline.
python scripts/benchmark_multi_camera.py \
  --project /path/to/four-camera-project \
  --warmup 10 --duration 60 \
  --baseline-json baseline.json \
  --output four-cameras.json
```

The script exits non-zero when a baseline was supplied and any camera is below
`threshold * baseline`. Without a baseline it still reports all measurements and
exits zero. It starts only the runtime and camera pipelines; the UI, websocket
server, and file server are not started. Stream and recording publication is
disabled by default so no full-frame MJPEG encoding competes with vision work;
pass `--streams` to measure that cost explicitly. The report records which mode
was used in `measurement.stream_publication`.

Each camera report includes:

- configured resolution, target FPS, and pixel format;
- `processed_fps` and `processed_frames` measured during the window;
- `capture_frames`, `dropped_capture_frames`, and `stale_capture_frames`;
- `dropped_stream_frames` from the bounded stream/record lane;
- `capture_latency_ms`, `process_latency_ms`, and
  `capture_to_result_latency_ms` at P50/P95/P99;
- `frame_bytes`, the decoded frame size handled by the pipeline; and
- `baseline_ratio` and `last_result_age_seconds`.

The top-level report adds aggregate FPS, mean FPS, worst/best camera FPS, FPS
spread, the 83% target, pass status, process CPU/RSS, host details, and USB
topology (`lsusb -t` where available). `mean_baseline_ratio` (also reported as
`aggregate_efficiency`) shows how close the whole set is to the single-camera
baseline: `1.0` means every camera matches the baseline. `fps_spread` and
`slowest_camera_index` show whether one camera is dragging the group down. If
aggregate FPS is high but one camera's FPS is low, that camera's
drop counters and result age identify whether it is starvation, pipeline cost,
or a bus-limited device. If all cameras drop together on one host controller,
the USB topology and frame size usually indicate bus saturation rather than
application serialization.
