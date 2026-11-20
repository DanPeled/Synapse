# Synapse sample project

This project is installed at `$HOME/Synapse` on release images and started by
the `synapse-runtime` systemd service.

It is deliberately minimal: the runtime starts without a camera, and cameras
can be added later through NetworkTables or the Synapse UI.

## Deploying changes

From a development machine:

```bash
cd synapse_imager/sample_project
python -m synapse_installer device add
python -m synapse_installer deploy
```

`device add` stores the device IP address and SSH password in
`.synapseproject`. The file is intentionally omitted from the image.
