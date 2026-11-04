---
description: A desktop app for discovering coprocessors, opening dashboards, and deploying projects.
icon: desktop
---

# Synapse Manager

Synapse Manager is an optional desktop app that finds Synapse devices on your network and gives you one-click access to their dashboard, SSH terminal, and project deployment.

You can do everything in this page with the command line. Synapse Manager just makes it faster.

## Install

Download the latest release from the [GitHub releases page](https://github.com/DanPeled/Synapse/releases).

Available formats:

| Platform | File |
| --- | --- |
| Linux | `.AppImage` or `.deb` |
| macOS | `.dmg` |
| Windows | `.msi` |

The app is built with Tauri and does not require a separate runtime.

## Discover devices

1. Open Synapse Manager.
2. Make sure your computer and the coprocessor are on the same network.
3. Press **Find Devices** or wait for the automatic scan.

The app sends a UDP discovery ping to port `45454` every five seconds. Devices running the Synapse runtime respond with:

- Hostname
- IP address
- Nickname
- Team number
- Runtime version
- SSH username

The table shows the **nickname** and **address** for each device.

{% hint style="info" %}
If no devices appear:

- Confirm the runtime is running on the device.
- Check that UDP port `45454` is not blocked by a firewall.
- Make sure both devices are on the same subnet.
- Try pinging the device by IP.
{% endhint %}

## Device actions

Each device row has action buttons:

| Action | What it does |
| --- | --- |
| **Info** | Shows hostname, IP, nickname, team number, version, and linked folder |
| **Open Dashboard** | Opens `http://<device-ip>:3000` in a new window |
| **Open Terminal** | Opens an SSH session to the device |
| **Deploy** | Deploys the linked project folder to the device |

### Link a project folder

The first time you deploy to a device, Synapse Manager asks you to choose the project folder. It remembers the choice for that device nickname.

From the device info dialog you can:

- **Open Folder** — open the linked project in your file manager.
- **Unlink** — forget the linked folder.

### Deploy

Deploy runs this command inside the linked folder:

```bash
python -m synapse_installer install <hostname>
```

Synapse Manager looks for a virtual environment first:

- Linux/macOS: `.venv/bin/python`, then `venv/bin/python`, then `python3`.
- Windows: `.venv\Scripts\python.exe`, then `venv\Scripts\python.exe`, then `python`.

If the installer is not available in that Python environment, deploy fails. Install `synapsefrc` in the project's virtual environment, or in the Python that Synapse Manager finds.

{% hint style="tip" %}
Synapse Manager passes the **hostname** the device reports to `synapse_installer install`. The installer matches that value against the names in the `deploy` section of `.synapseproject`, so keep the device entry named after its hostname. If your entry uses a different name, deploy from a terminal with that name instead.
{% endhint %}

## When to use the CLI instead

Use the command line if you:

- Need to deploy to several devices at once.
- Want deploy output in a terminal you control.
- Are setting up CI.
- Need to run `sync` or `device add` directly.

See [Project Management](README.md) for the CLI reference.

## Troubleshooting

- **Deploy says the installer is missing** — install `synapsefrc` in the linked project's virtual environment.
- **Device does not appear** — check the firewall and network, then verify the runtime is running.
- **Dashboard does not open** — confirm port `3000` is reachable and the device IP has not changed.
- **Terminal does not open** — make sure SSH is enabled and your terminal application is installed.

More help is in [Troubleshooting](../../additional-resources/troubleshooting.md).
