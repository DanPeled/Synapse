---
description: How to choose a coprocessor, camera, storage, and power supply for Synapse.
icon: microchip
---

# Selecting Hardware

There is no single "correct" Synapse setup. The right choice depends on how many cameras you need, which pipelines you run, and how much space and power your robot has.

## Coprocessor

The coprocessor runs the Synapse runtime and does all vision processing.

### Minimum requirements

- 64-bit ARM or x86 Linux.
- At least 4 GB of RAM (8 GB recommended if you run multiple cameras or large models).
- A USB 3.0 port for a USB camera, or a CSI camera connector.
- Ethernet or Wi-Fi.
- SSH access and `sudo`.
- Python 3.11–3.14 available, or enough CPU and time to build Python from source.

### Recommended devices

| Device | Strengths | Things to know |
| --- | --- | --- |
| **Orange Pi 5** | Fast CPU, NPU, good price, 4/8/16 GB options | Needs a 5V/4A supply; some images need extra setup for Wi-Fi |
| **Raspberry Pi 5** | Widely available, strong ecosystem, 2× USB 3.0 | Needs a 5V/5A supply; active cooling strongly recommended |
| **Orange Pi 5 Plus** | More I/O and dual Ethernet | Larger and more expensive |
| **Mini PC (x86)** | Easiest compatibility, fastest CPU | Higher power draw and weight |

{% hint style="info" %}
Any Linux-compatible device can work as long as it meets the requirements in [Deploying on Custom Hardware](deploying-on-custom-hardware.md). The device does not need a desktop environment.
{% endhint %}

### CPU vs. NPU

Most Synapse pipelines use OpenCV and the CPU. An NPU is only useful if your custom pipeline uses a model that can target it. For AprilTag and color detection, single-core CPU performance matters more than NPU performance.

## Camera

The camera has a large effect on vision quality.

### Global shutter vs. rolling shutter

- **Global shutter** cameras capture every pixel at once. This is strongly preferred for AprilTag detection on a moving robot, because rolling-shutter cameras can skew tags and reduce pose accuracy.
- **Rolling shutter** cameras are common and cheaper, but may produce more jitter and missed detections while the robot moves quickly.

### Resolution and frame rate

- Higher resolution improves long-range AprilTag detection but costs CPU time.
- 1280×720 is a common starting point for AprilTag pipelines.
- 640×480 is often enough for color detection and is much faster.
- Match the camera's configured resolution to the resolution you calibrated. Calibration data is stored per resolution.

### Field of view

A wider field of view lets the camera see more tags, but each tag occupies fewer pixels. A 70°–90° horizontal field of view is typical.

### Focus and exposure

- Use a camera with **manual focus** if possible, and lock the focus after aiming.
- Disable **auto-exposure** or lock it once tuned. Changing exposure changes brightness and can hurt detection stability.

## Storage

- Use a reputable microSD card (A1/A2 rated) or, better, an NVMe SSD on devices that support one.
- 16 GB is enough for the runtime; 32 GB or more is safer if you record video.
- Recordings are written to a `records/` folder on the device and can fill the card quickly.

## Power

- Use a regulated 5V supply that can provide the device's rated current.
- On a robot, use a dedicated 5V regulator (for example a Pololu S13V30F5 or a Zinc V) rather than the RoboRIO's 5V rail.
- Add a capacitor or use a regulator with good transient response if the device reboots when motors start.
- See [Wiring](../quick-start/wiring.md) for diagrams.

## Networking

- Prefer Ethernet for the camera and coprocessor connection when possible.
- If you use Wi-Fi, use a 5 GHz network and keep the coprocessor close to the access point.
- Reserve a static IP or DHCP lease so the dashboard URL does not change.

## Cooling

Vision workloads keep the CPU busy. Use a heatsink and fan on passively cooled boards. Thermal throttling shows up as steadily increasing latency and dropped frames.

## Next steps

- [Deploying on Custom Hardware](deploying-on-custom-hardware.md)
- [Performance Matrix](performance-matrix.md)
- [Common Hardware Setups](../quick-start/common-hardware-setups.md)
