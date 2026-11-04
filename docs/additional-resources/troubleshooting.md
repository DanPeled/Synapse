---
icon: cauldron
---

# Troubleshooting

This page covers the problems teams hit most often. Start with the section that matches the symptom.

## First steps

1. Open the dashboard at `http://<device-ip>:3000`.
2. Check the **Settings** page for device status, network settings, and free disk space.
3. Open **View Program Logs** (or press `~`) and look for errors.
4. If the runtime starts from a terminal, read the terminal output. Python tracebacks appear there.

For a bug report, include the runtime version, device hardware, the log output, and the steps that reproduce the problem.

## The dashboard will not load

| Check | What to do |
| --- | --- |
| Device reachable | `ping <device-ip>` from your computer |
| Correct address | The runtime publishes its address under NetworkTables `web_ui` |
| Port | The dashboard uses port `3000`. Make sure your firewall allows it. |
| Runtime running | Check the device's terminal or service status |
| Same network | Your computer and the coprocessor must be on the same network |

If you are running on a laptop, try `http://localhost:3000`.

If the page loads but the camera stream is blank, refresh the browser. The stream is served over HTTP starting at port `1180`.

## No cameras found

1. Check the camera is connected and powered.
2. On Linux, list video devices:

```bash
ls /dev/video*
```

3. If you use two identical cameras, give them distinct device names or UIDs.
4. Restart the runtime after plugging in a camera.
5. Check the camera is not already in use by another program.

Camera detection depends on the OS and driver. Some cameras expose multiple device nodes; try each one.

## Robot code sees no data

Work through this list in order:

1. **Team number** — The runtime must connect to the NetworkTables server at your team's address (`10.TE.AM.2`). Check the **Settings** page.
2. **Root table** — The runtime's **NetworkTable** value must match the name passed to `SynapseCamera`. The default is `Synapse`.
3. **Camera name** — The name passed to `SynapseCamera` must match the camera nickname in the dashboard.
4. **Pipeline type** — Call `getPipelineType()` and confirm it matches the result class you are decoding.
5. **Results published** — The pipeline may not have produced a result yet. Check for `hasResults` or look at the dashboard results panel.
6. **Network** — The RoboRIO and coprocessor must be on the same network and able to reach each other.

{% hint style="info" %}
If the runtime is in `--server` mode, it hosts its own NetworkTables server. Your robot code must connect to that server, not the RoboRIO.
{% endhint %}

## AprilTags are not detected

| Cause | Fix |
| --- | --- |
| Wrong tag family | Match `tag_family` to your tags (`tag36h11` or `tag16h5`) |
| Tag too small or far away | Move closer, increase resolution, or lower `quad_decimate` |
| Blurry or dark image | Improve lighting, focus the lens, increase exposure |
| Crop excludes the tag | Check `crop_x` and `crop_y` |
| Tags filtered out | Check `min_cluster_pixels`, `max_line_fit_mse`, `min_white_black_diff` |
| Wrong field map | Replace `deploy/fmap.json` with the map for your field |
| Detection is disabled by `critical_angle` | See [Known Issues](known-issues.md) |

Start from the defaults and change one setting at a time.

## Robot pose is wrong or jittery

1. **Tag size** — `tag_size` must match the physical tag size in meters. The default `0.1651` is 6.5 inches.
2. **Calibration** — Calibrate at the resolution the pipeline uses.
3. **Field map** — The tag IDs and poses in `deploy/fmap.json` must match your field.
4. **Mount offset** — For robot pose, set `robotToCameraOffset` accurately. A few centimeters of error becomes a large field error.
5. **Single tag** — One tag gives an ambiguous pose. Prefer multiple tags, reject high `reprojection_error`, and fuse with odometry.

## Settings do not stick

- Press **Save** in the dashboard. Changing a value only updates the running pipeline.
- Deploys preserve the remote `config/` folder. A factory reset or import replaces it.
- If you import settings, use a `.zip` file. The picker also accepts `.json`, but only `.zip` is handled.
- If NetworkTables is writing the setting every loop, it can overwrite dashboard changes.

## Deploy or install fails

| Symptom | Fix |
| --- | --- |
| `Not in a Synapse project` | Run the command from the project root that contains `.synapseproject` |
| SSH connection refused | Check the hostname, username, password, and network |
| Permission denied | Confirm the device user can write to the Synapse folder |
| Files missing on device | Run `install` (which runs `sync` then `deploy`) instead of `deploy` alone |
| Wrong device | Use `device add` to add or update the device configuration |

Useful commands:

```bash
python -m synapse_installer install <device-nickname>
python -m synapse_installer sync <device-nickname>
python -m synapse_installer deploy
```

The nickname is the key under `deploy` in `.synapseproject`. Pass it to `sync` and `install`; `deploy` without a name targets every device.

## Simulation will not start

- Install Chrome or Chromium.
- Set `SYNAPSE_CHROME` to the executable path if auto-detection fails.
- Try a different ANGLE backend with `SYNAPSE_SIM_ANGLE=gl`.
- Enable `SYNAPSE_SIM_DEBUG=1` for more output.
- Make sure Vulkan or the chosen backend is installed on Linux.

See [Simulation](../usage/simulation.md) for details.

## Python import errors

| Error | Fix |
| --- | --- |
| `No module named synapse` | Install `synapsefrc` in the active environment |
| `No module named synapselib` | Install the Python SynapseLib from `synapse_lib/py` |
| Python version error | Use Python 3.11–3.14 |
| `No module named ntcore` | Install RobotPy or `pyntcore` |
| `No module named wpimath` | Install `robotpy_wpimath` |

Check which interpreter you are using:

```bash
python -c "import sys; print(sys.executable); print(sys.version)"
```

## Performance is poor

- Lower the pipeline resolution.
- Reduce `max_fps`.
- Disable recording when you do not need it.
- Lower `quad_decimate` only if detection quality needs it; raising it improves speed.
- Check CPU and memory on the **Settings** page.
- On Windows, camera performance may be worse than on Linux. See [Known Issues](known-issues.md).

## Still stuck

- Search [GitHub issues](https://github.com/DanPeled/Synapse/issues).
- Open a new issue with logs and reproduction steps.
- Check [Known Issues](known-issues.md) before filing.

## Next steps

- [Known Issues](known-issues.md)
- [NetworkTables API](networktables-api.md)
- [Settings Page](../usage/built-in-pipelines-1/settings-page.md)
