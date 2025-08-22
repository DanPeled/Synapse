---
icon: hands-holding-circle
---

# Project Management

In order to create a new project on your local machine, you will need to run the following command:

```bash
<pythonexec> -m synapse_installer create
```

Then you will be prompted to enter project details inside of the TUI, and will prompt to create a coprocessor config.

Config variables include:

* Project name
* Base coprocessor config

## Adding Processors

In order to add an additional processor onto the config to be able to deploy code onto it inside of an already created you can either modify the `deploy` section inside of the `.synapseproject` metadata file created inside of the project directory or call the following command:

```bash
<pythonexec> -m synapse_installer device add
```

This command will prompt to add a device config the same way the project creation would.

## Automatic Processor Discovery

coming soon...
