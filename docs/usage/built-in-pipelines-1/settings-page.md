---
description: Device information, hardware metrics, network configuration, logs, and maintenance actions.
icon: gear
---

# Settings Page

The Settings page contains device information, network configuration, logs, and maintenance actions. Open it from the sidebar at `http://<device-ip>:3000`.

## Device status

### Device info

The device info table shows:

| Field | Meaning |
| --- | --- |
| **Version** | The Synapse runtime version |
| **Platform** | The operating system type reported by the device |
| **IP Address** | The address the runtime is using |

The **Last Fetched** badge shows when the page last received hardware metrics.

### Hardware metrics

The metrics table shows:

| Metric | Notes |
| --- | --- |
| **CPU Temp** | Shows `---` when the device does not expose a temperature sensor |
| **CPU Usage** | Percentage of total CPU in use |
| **Memory Usage** | Used RAM as a percentage of total RAM |
| **Uptime** | Time since the device booted |
| **Disk Usage** | Percentage of the root disk in use |

{% hint style="info" %}
Some metrics are device-specific and may show `---` on unsupported hardware. For example, GPU and NPU metrics are only available on some boards.
{% endhint %}

## Network settings

The network settings card controls how the device connects to your robot network.

| Field | What it does |
| --- | --- |
| **Team Number** | The FRC team number. The runtime connects to the NetworkTables server at that team's address (`10.TE.AM.2`). |
| **NetworkTable** | The root NetworkTables table name Synapse publishes under. Defaults to `Synapse`. |
| **Manage Device Networking** | Enables or disables changes to the device's network configuration |
| **IP Mode** | `DHCP` or `Static` |
| **Static IP** | The address to assign when using static mode. The subnet mask is fixed at `/24`. |
| **Hostname** | The device's hostname on the local network |
| **NetworkManager Interface** | Which network interface the address is applied to |

### Team number

The team number must match your robot. If it is wrong, the runtime will not connect to the RoboRIO's NetworkTables server, and robot code will not see any data.

### NetworkTable

This is the root table name. Default: `Synapse`.

Robot code must use the same name:

```java
SynapseCamera camera = new SynapseCamera("camera0", "Synapse");
```

If you change this value, change the coprocessor name in robot code to match.

### DHCP vs static

- **DHCP** lets the router assign an address. The address may change after a reboot.
- **Static** keeps the same address. Synapse adds the static address to the selected interface and also runs `dhclient` on that interface.

{% hint style="warning" %}
Changing network settings requires a runtime restart. The page warns you that the new values take effect after restarting. Make sure the new address is reachable before you disconnect.
{% endhint %}

Press **Save** in the network card to apply the changes.

## Device control

The device control card contains:

| Action | What it does |
| --- | --- |
| **Import Settings** | Replaces the device's `config/` folder from a ZIP file |
| **Export Settings** | Downloads the device's `config/` folder as a ZIP |
| **Download Logs** | Downloads the runtime logs as a ZIP |
| **View Program Logs** | Opens the live log viewer |

### Import settings

1. Press **Import Settings**.
2. Select a `.zip` file containing a `config/` folder.
3. Confirm the replacement.

The import **replaces the entire config folder** and then restarts Synapse. Use it to restore a backup or copy tuning from another device.

{% hint style="warning" %}
The file picker accepts `.json` and `.zip`, but only `.zip` is currently handled. Selecting a JSON file shows an error. Export settings first so you have a backup before importing.
{% endhint %}

### Export settings

Downloads the current `config/` folder as `settings.zip`. This contains:

- `settings.yml`
- Per-camera `camera_configs.yml`
- Per-camera `pipeline_settings.yml`

### Logs

Press **Download Logs** to download the log folder as a ZIP. Press **View Program Logs** to open the live log viewer.

The log viewer can filter by level:

- Info
- Warning
- Error

You can also open the log viewer with the tilde key (`~`) or backtick (`` ` ``).

## Danger zone

{% hint style="danger" %}
These actions interrupt the runtime or erase data. Read the confirmation dialog before continuing.
{% endhint %}

| Action | What it does |
| --- | --- |
| **Restart Synapse** | Restarts the runtime process |
| **Restart Device** | Reboots the coprocessor |
| **Factory Reset Synapse & Delete Everything** | Deletes all saved settings and configuration, then restarts |

Factory reset removes the runtime's saved state and returns it to defaults. Calibration and tuned settings are lost. Export your settings first if you might need them.

## Next steps

- [Pipeline Settings](pipeline-settings.md)
- [Camera Page](camera-page.md)
- [Networking](../../getting-started/quick-start/networking.md)
- [Troubleshooting](../../additional-resources/troubleshooting.md)
