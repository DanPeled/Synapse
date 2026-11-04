---
description: Proven coprocessor, camera, storage, and power combinations for Synapse.
icon: gears
---

# Common Hardware Setups

This page lists hardware that is commonly used with Synapse. It is not a compatibility guarantee. If you use something else, check [Deploying on Custom Hardware](../hardware-selection/deploying-on-custom-hardware.md).

## Coprocessors

### Orange Pi 5

- 2× USB 2.0 ports, 1× USB 3.0 port.
- Up to 2.4 GHz CPU.
- 4 GB, 8 GB, or 16 GB of RAM.
- Powered by USB-C at 5V/4A, or through the GPIO header.
- NPU available for custom models.

### Raspberry Pi 5

- 2× USB 2.0 ports, 2× USB 3.0 ports.
- Up to 2.4 GHz CPU.
- Up to 16 GB of RAM.
- Powered by USB-C at 5V/5A, or through the GPIO header.
- PoE+ with a separate PoE+ HAT.

{% hint style="info" %}
Synapse works on any Linux-compatible device that meets the requirements in [Deploying on Custom Hardware](../hardware-selection/deploying-on-custom-hardware.md). The two boards above are simply common choices.
{% endhint %}

## Cameras

### Recommended: global-shutter USB camera

Examples: Arducam OV9281, OV2311, or similar mono/color global-shutter modules.

- Best AprilTag accuracy while the robot moves.
- Usually appears as `/dev/video*`.
- Choose a lens that gives roughly 70°–90° horizontal field of view.

### Common: rolling-shutter USB webcam

Examples: Logitech C920, C270, or similar.

- Cheap and easy to find.
- Fine for color detection and slow-moving AprilTag use.
- Can produce motion skew and missed detections at high robot speeds.

### CSI cameras

Raspberry Pi and Orange Pi camera modules connect through CSI instead of USB.

- Lower latency and less USB bandwidth.
- Requires the correct device-tree overlay and driver.
- Not every CSI camera is supported by every board image.

{% hint style="tip" %}
Prefer a camera with **manual focus** and **manual exposure**. Lock both after tuning, or detection stability will change as lighting changes.
{% endhint %}

## Storage

- 16 GB minimum, 32 GB or more recommended.
- Use a reputable A1/A2 microSD card, or an NVMe SSD if the board supports it.
- Recording video fills storage quickly. Check free space before a long practice session.

## Power

Recommended regulators and wiring:

- **Orange Pi 5** — Zinc V, Pololu S13V30F5, or a 5V/4A USB-C supply.
- **Raspberry Pi 5** — Zinc V USB-C, or a 5V/5A USB-C supply.

On a robot:

- Wire the regulator directly to the power distribution board, not through the RoboRIO's 5V rail.
- Use locking connectors or hot glue the barrel/USB-C connector.
- Add strain relief so vibration does not unplug the device mid-match.

See [Wiring](wiring.md) for diagrams.

## Network

- A network switch is strongly recommended on the robot.
- Use Ethernet between the coprocessor, RoboRIO, and radio when possible.
- If you use Wi-Fi, use 5 GHz and keep the device close to the access point.

## Example setups

### Budget AprilTag setup

- Raspberry Pi 5 (8 GB).
- Arducam OV9281 global-shutter camera.
- 32 GB A2 microSD.
- 5V/5A USB-C supply or Zinc V regulator.

### Multi-camera setup

- Orange Pi 5 Plus or a small x86 mini PC.
- Two USB 3.0 global-shutter cameras.
- NVMe SSD.
- Active cooling.
- Gigabit network switch.

## Next steps

- [Wiring](wiring.md)
- [Networking](networking.md)
- [Selecting Hardware](../hardware-selection/selecting-hardware.md)
