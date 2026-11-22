---
description: Measure how well several cameras run at the same time and find out what limits them.
icon: gauge-high
---

# Multi-Camera Performance

Synapse can run several cameras at once. Once you use more than one camera, the limit is often the USB connection, not the vision pipeline. This page explains how to measure that and what the results mean.

## The target

Measure one camera first. That is your **baseline**. Then measure the same setup with four cameras.

The four-camera setup passes when the slowest camera still reaches at least **83%** of the single-camera rate:

```text
slowest camera FPS >= 0.83 × single-camera FPS
```

If one camera at 120 FPS gives the baseline, the target is about 100 FPS for each of the four cameras.

83% is a floor, not a goal to stop at. Higher is always better.

## Why USB matters

Many FRC OV9782 camera modules advertise 1280x720 at 120 FPS in MJPEG over USB 2.0. That is the mode used for this benchmark. Uncompressed video would use far more bandwidth and is not practical for four cameras.

A single USB 2.0 bus has about 53 MB/s of theoretical throughput. Every device behind the same host controller shares that bandwidth, and real payload throughput is lower. If the MJPEG frames get larger because of the scene, four cameras may not fit on one bus.

This matters when you read the results:

- If all four cameras slow down together and they share one USB controller, the bus is probably full.
- If one camera is much slower than the others, check that camera's cable, port, resolution, and pipeline.
- If every camera drops when a stream is enabled, live-view encoding is using CPU or USB bandwidth.

## What Synapse does to keep cameras independent

The runtime gives each camera its own capture and processing lane. It keeps only the newest frames instead of building a backlog, and it does stream and recording writes off the camera thread. It also records dropped frames and stale frames so you can see when frames are being skipped.

Software cannot make a shared USB bus carry more data. When the bus is full, the benchmark reports the shortfall instead of hiding it.

## Run the benchmark

The benchmark script is in the Synapse source checkout. Run it from that checkout in a Python environment that has the Synapse dependencies installed.

Prepare two project folders:

- a project with only the camera you want to measure for the baseline;
- a project with all four cameras, using the same resolution, frame rate, and pipeline.

If a project has no `config/settings.yml` yet, start the runtime once to create it.

First, measure the single camera:

```bash
python scripts/benchmark_multi_camera.py \
  --project /path/to/single-camera-project \
  --warmup 10 --duration 60 \
  --output baseline.json
```

Then measure four cameras against that baseline:

```bash
python scripts/benchmark_multi_camera.py \
  --project /path/to/four-camera-project \
  --warmup 10 --duration 60 \
  --baseline-json baseline.json \
  --output four-cameras.json
```

The script exits with an error if a baseline was supplied and any camera is below the target. Without a baseline, it still writes a full report and exits normally.

The benchmark starts only the runtime and pipelines. It does not start the dashboard, WebSocket server, or file server. Stream and recording publication is disabled by default so live-view encoding does not compete with vision work. Add `--streams` to measure that cost. The report records which mode was used.

### Useful options

| Option | What it does |
| --- | --- |
| `--project` | Synapse project folder. Defaults to the current folder |
| `--warmup` | Seconds to run before counting. Default: `10` |
| `--duration` | Seconds to measure. Default: `60` |
| `--baseline-json` | Earlier report to read the single-camera baseline from |
| `--baseline-fps` | Single-camera FPS to use when you do not have a report |
| `--threshold` | Required fraction of baseline. Default: `0.83` |
| `--streams` | Keep stream and recording publication enabled |
| `--output` | Write the JSON report to a file |

## Read the report

For each camera, the report includes:

- configured resolution, target FPS, and pixel format;
- `processed_fps` and `processed_frames`;
- captured, dropped, and stale frame counts;
- dropped stream or recording frames;
- capture, process, and capture-to-result latency at P50, P95, and P99;
- frame size and the age of the newest result;
- `baseline_ratio`, which is that camera's FPS divided by the baseline.

The top level adds:

- total, mean, and max camera FPS;
- slowest and fastest camera indexes;
- `fps_spread`;
- the aggregate target FPS;
- `aggregate_efficiency` (also called `mean_baseline_ratio`), where `1.0` means every camera matches the baseline;
- pass/fail status against the 83% target;
- CPU use and peak memory use;
- USB topology when `lsusb -t` or an equivalent tool is available.

`capture_to_result_latency_ms` measures the time from the camera timestamp to a finished result. It includes waiting in the capture queue, pipeline time, and publishing time.

## Fixing a failed run

1. Check the USB topology. Split cameras across separate host controllers when you can.
2. Confirm the cameras are using MJPEG, not YUY2 or another uncompressed format.
3. Lower resolution or FPS if the frame size is too large for the bus.
4. Run the baseline again with the same settings after any change.
5. Use `--streams` only when you need to know the cost of live-view publication.
6. Check dropped and stale counters for one camera that lags behind the others.

## Next steps

- [Selecting Hardware](selecting-hardware.md)
- [Performance Matrix](performance-matrix.md)
- [Troubleshooting](../../additional-resources/troubleshooting.md)
