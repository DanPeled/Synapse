---
icon: circle-play
---

# Quick Start

This checklist takes you from an unopened coprocessor to a working camera pipeline. Follow the links for details.

{% hint style="info" %}
New to Synapse? Read [How Synapse Works](../how-synapse-works.md) first. It explains the runtime, pipelines, and how robot code receives results.
{% endhint %}

## Before you start

- [ ] An Orange Pi 5, Raspberry Pi 5, or another supported Linux coprocessor.
- [ ] A camera (USB or CSI) and the correct cable.
- [ ] A microSD card and a way to image it.
- [ ] A stable 5V power supply or a robot power regulator.
- [ ] A development computer with Python 3.11–3.14 and Git.
- [ ] Internet access on both the coprocessor and your development computer.

## 1. Choose and prepare your hardware

1. Read [Common Hardware Setups](common-hardware-setups.md) to pick a coprocessor and camera.
2. Wire the coprocessor safely with [Wiring](wiring.md).
3. Image the device, then connect it to your network. See [Installing Software](../installing-software.md) and [Networking](networking.md).

## 2. Install Synapse on your development computer

```bash
python -m pip install --upgrade synapsefrc
```

Verify the installer is available:

```bash
python -m synapse_installer --help
```

You should see `create`, `deploy`, `sync`, `install`, and `device` commands.

## 3. Create a project

```bash
python -m synapse_installer create
```

The interactive prompt asks for:

- A project name.
- Whether to configure a coprocessor now.

If you configure a coprocessor, provide its hostname, IP address, and SSH password. You can add more devices later with `python -m synapse_installer device add`.

This creates:

```text
<project-name>/
├── .synapseproject
├── main.py
├── pyproject.toml
├── pipelines/
└── deploy/
```

{% hint style="warning" %}
The generated `main.py` imports `from synapse.core import Synapse`, which currently fails. Change that line to `from synapse.core.synapse import Synapse` before running or deploying the project. See [Known Issues](../../additional-resources/known-issues.md#generated-mainpy-has-a-broken-import).
{% endhint %}

## 4. Install and deploy to the coprocessor

From inside the project folder:

```bash
python -m synapse_installer install <device-nickname>
```

Use the device nickname you set during `create`. It defaults to the device hostname.

`install` runs two steps:

1. **Sync** — installs system packages, creates a Python virtual environment on the device, and installs Synapse.
2. **Deploy** — copies your project to `~/Synapse` and starts the `synapse-runtime` service.

The first run can take several minutes because Python and OpenCV are installed on the device.

{% hint style="warning" %}
The device needs internet access during the first sync. If the device cannot reach the internet, install the packages manually or use a device image that already includes them.
{% endhint %}

## 5. Open the dashboard

In a browser on the same network, open:

```text
http://<device-ip>:3000
```

You can also run this on the coprocessor to print the address:

```bash
hostname -I
```

The dashboard shows a live camera feed, the pipeline selector, settings, and results.

## 6. Pick a pipeline

1. Open the **Dashboard**.
2. Select your camera.
3. Use the pipeline dropdown to choose **ApriltagPipeline** or **ColorPipeline**.
4. If you need a different pipeline, use **Add Pipeline**.

See [UI Interaction](../../usage/built-in-pipelines-1/README.md) for a tour.

## 7. Calibrate your camera (recommended)

AprilTag pose estimates are much more accurate after calibration.

1. Open the **Camera** page.
2. Choose the resolution you will use in your pipeline.
3. Press **Calibrate** and follow the on-screen instructions.
4. Print the Charuco board described in [Camera Calibration](camera-calibration.md).

## 8. Read results from robot code

Add SynapseLib to your robot project:

- Java: install the vendordep from [Installing SynapseLib](../../robot-interfacing/synapse-bridge/installing-synapse-bridge.md).
- Python: install the `synapsefrclib` package from the repository.

Then read results:

```java
SynapseCamera camera = new SynapseCamera("camera0", "Synapse");
Optional<ApriltagResult> result = camera.getResults(SynapsePipelineType.kApriltag);
```

See [Getting Target Data](../../robot-interfacing/synapse-bridge/getting-target-data.md).

## No robot or coprocessor yet?

You can run everything on your laptop with simulated cameras:

```bash
python main.py --sim --server
```

See [Simulation](../../usage/simulation.md).

## Troubleshooting

If something does not work:

- Check that the runtime is running: `sudo systemctl status synapse-runtime`.
- Watch the logs in the UI, or run `journalctl -u synapse-runtime -f` on the device.
- Confirm the coprocessor and laptop are on the same network.
- Check the team number in the [Settings Page](../../usage/built-in-pipelines-1/settings-page.md).

More help is in [Troubleshooting](../../additional-resources/troubleshooting.md).
