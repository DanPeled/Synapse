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
| **Static Address** | Adds a fixed IPv4 address alongside DHCP so the robot network can always reach the device. DHCP stays enabled for internet access. |
| **Static IP** | The static address to add, for example `10.12.34.11`. Shown when **Static Address** is enabled. |
| **CIDR prefix** | Prefix length entered after `/`, from `1` to `32`. Defaults to `24`. |
| **Hostname** | The device's hostname on the local network |
| **Network Interface** | Physical interface for the static address. Virtual interfaces such as `lo`, Docker bridges, VPNs, and `tailscale` are hidden. |

### Team number

The team number must match your robot. If it is wrong, the runtime will not connect to the robot controller's NetworkTables server, and robot code will not see any data.

### NetworkTable

This is the root table name. Default: `Synapse`.

Robot code must use the same name:

```java
SynapseCamera camera = new SynapseCamera("camera0", "Synapse");
```

If you change this value, change the coprocessor name in robot code to match.

### DHCP and static addresses

- **DHCP** assigns an address from the router. It can change after a reboot, but it keeps internet access working.
- **Static Address** adds a secondary IPv4 address on the selected physical interface while DHCP remains enabled. The device is then reachable at both addresses.

When you enable **Static Address**, Synapse suggests an address based on the team number (for example `10.12.34.11` for team 1234). You can accept the suggestion or enter your own valid host address. Network and broadcast addresses are rejected, as are loopback, link-local, multicast, and reserved addresses.

Turning **Static Address** off removes only the static address. DHCP is not disabled, so internet access is unaffected.

Synapse uses NetworkManager when it is running, then netplan, then a generic `ip addr` fallback that reapplies the address if the interface resets. The address is saved in `config/settings.yml` and reapplied on startup; the legacy `interfrace` key is still read from older configs.

Press **Save** to open a confirmation dialog showing the address, prefix, and interface that will be applied. Applying the change can briefly drop the connection to the device. Team number and NetworkTables table changes take effect after a runtime restart; the other network settings apply immediately.

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
