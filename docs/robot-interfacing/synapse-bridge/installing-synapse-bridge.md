---
description: Install the SynapseLib vendordep for Java or the synapselib package for Python.
icon: download
---

# Installing SynapseLib

Choose the tab for your robot language.

{% tabs fullWidth="true" %}
{% tab title="Java" %}
Java projects use a WPILib **vendordep**. The vendordep tells GradleRIO where to download the library and its dependencies.

{% hint style="warning" %}
For the 2027 alpha, use the current `dev` vendordep below. The pinned `SynapseLib-2027.0.0a1.json` URL listed in the alpha release notes is not published yet. See [Known Issues](../../additional-resources/known-issues.md#2027-alpha-java-vendordep-is-not-published).
{% endhint %}

### Install from VS Code

1. Open your robot project in VS Code with the WPILib extension installed.
2. Open the Command Palette (`Ctrl+Shift+P`).
3. Run **WPILib: Manage Vendor Libraries**.
4. Choose **Install new libraries (online)**.
5. Paste this URL:

```text
https://danpeled.github.io/Synapse/SynapseLib-dev.json
```

6. Press Enter and let Gradle sync.

### Install manually

Download the JSON file:

{% embed url="https://danpeled.github.io/Synapse/SynapseLib-dev.json" %}

Save it as `vendordeps/SynapseLib.json` inside your robot project, then run a Gradle build or restart VS Code.

### Verify

Add an import to a robot class:

```java
import synapse.SynapseCamera;
```

If Gradle reports no errors, the vendordep is installed.

{% hint style="info" %}
The `dev` vendordep tracks the current 2027 alpha code and targets WPILib 2027 alpha 8, GradleRIO 2027, Gradle 9.2.0, and Java 25. It may change between builds. For a stable 2026 project, use `https://danpeled.github.io/Synapse/SynapseLib-2026.0.1.json` instead.
{% endhint %}
{% endtab %}

{% tab title="Python" %}
The Python library is published as `synapsefrclib` and imported as `synapselib`.

### Requirements

- Python `>=3.11, <=3.14`
- RobotPy `2027.0.0a6` with `pyntcore` and `robotpy_wpimath`
- `msgpack`

The installer pulls these dependencies in automatically.

### Install from the Synapse repository

The package is not published on PyPI, so install it from a local clone:

```bash
git clone https://github.com/DanPeled/Synapse.git
pip install ./Synapse/synapse_lib/py
```

If you already have the repository checked out:

```bash
pip install ./synapse_lib/py
```

Install into the same virtual environment your RobotPy project uses, so `robotpy deploy` includes the package on the robot.

### Build a wheel for offline installs

```bash
pip wheel ./synapse_lib/py -w dist
pip install dist/synapsefrclib-*.whl
```

### Verify

```python
from synapselib import SynapseCamera, SynapsePipelineType
```

If the import succeeds, the library is installed.

{% hint style="warning" %}
The Python package is versioned `2027.0.0a1` and pins RobotPy `2027.0.0a6`. The matching pinned Java vendordep is not published yet, so use the `dev` vendordep for Java 2027 alpha projects. Pin the versions you test with and reinstall after updating the repository.
{% endhint %}
{% endtab %}
{% endtabs %}

## Updating

{% tabs %}
{% tab title="Java" %}
Run **WPILib: Manage Vendor Libraries** → **Check for updates (online)**, or replace `vendordeps/SynapseLib.json` with a newer version and rebuild.
{% endtab %}

{% tab title="Python" %}
Pull the repository and reinstall:

```bash
git pull
pip install --force-reinstall ./synapse_lib/py
```
{% endtab %}
{% endtabs %}

## Next steps

- [Getting Target Data](getting-target-data.md)
- [Robot Pose](robot-pose.md)
- [Runtime Camera Settings](runtime-camera-settings.md)
