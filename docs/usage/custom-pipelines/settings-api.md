---
description: Define validated pipeline settings that become controls in the dashboard.
icon: sliders-up
---

# Settings API

The Settings API connects Python settings classes to the dashboard, to NetworkTables, and to validation. You define a field once, and Synapse generates the control, validates every change, and stores the value.

## Defining a settings class

Subclass `PipelineSettings` and declare fields with `settingField`:

```python
from synapse import Pipeline, PipelineSettings
from synapse.core.settings_api import NumberConstraint, settingField


class MyPipelineSettings(PipelineSettings):
    circle_size = settingField(
        NumberConstraint(minValue=0, maxValue=500, step=1),
        default=20,
        description="Radius of the circle in pixels.",
        category="<Circle/> Drawing",
    )


class MyPipeline(Pipeline[MyPipelineSettings]):
    def __init__(self, settings: MyPipelineSettings):
        super().__init__(settings)
```

`settingField` takes:

| Argument | Required | Meaning |
| --- | --- | --- |
| `constraint` | Yes | The rule that validates the value |
| `default` | Yes | The starting value |
| `description` | No | Tooltip text in the dashboard |
| `category` | No | Tab the setting appears under |

The attribute name becomes the setting key. In the example, `circle_size` is the key used in the dashboard, in `config/`, and in NetworkTables.

{% hint style="warning" %}
Do not use a settings class without passing it to `Pipeline[...]`. If the generic argument is missing, Synapse falls back to the base `PipelineSettings` and your fields are not registered.
{% endhint %}

## Reading and writing settings

Inside a pipeline:

```python
# Read by Setting object (recommended, type-checked)
size = self.getSetting(MyPipelineSettings.circle_size)

# Read by key
size = self.getSetting("circle_size")

# Write by Setting object or key
self.setSetting(MyPipelineSettings.circle_size, 40)
self.setSetting("circle_size", 40)
```

Values that fail validation are rejected. Valid values are normalized before they are stored. For example, a number is snapped to the nearest allowed step.

## Categories and icons

The `category` string groups settings into tabs. You can prefix the label with a Lucide icon name inside angle brackets:

```python
category="<Circle/> Drawing"
```

The dashboard renders a `Drawing` tab with a circle icon. The text after `/>` is the label. If you omit the category, the setting appears in the default group.

Built-in camera properties use the category `<Camera/> Camera Properties`.

## Constraint types

### `NumberConstraint`

A number, optionally bounded and stepped.

```python
NumberConstraint(minValue=0, maxValue=255, step=1)
NumberConstraint(minValue=0, maxValue=None)
```

| Argument | Meaning |
| --- | --- |
| `minValue` | Minimum allowed value, or `None` for no minimum |
| `maxValue` | Maximum allowed value, or `None` for no maximum |
| `step` | Increment, or `None` for any value |

When both `minValue` and `maxValue` are set, the dashboard renders a slider. Otherwise it renders a number input.

If `step` is set and the value does not land on a step, the value is snapped to the nearest step. **The minimum is used as the step origin.** If `minValue` is `None`, step snapping is skipped.

### `RangeConstraint`

A pair of numbers, used for a range such as crop bounds.

```python
RangeConstraint(minValue=-1, maxValue=1, step=0.01)
```

The value must be a list or tuple of two numbers. The dashboard renders a two-handle range slider.

```python
crop_x = settingField(
    RangeConstraint(minValue=-1, maxValue=1, step=0.01),
    default=[-1, 1],
    category="<Funnel/> Filtering",
)
```

### `BooleanConstraint`

A true/false value.

```python
BooleanConstraint()                    # Toggle
BooleanConstraint(renderAsButton=True) # Button
```

`renderAsButton=True` is useful for actions such as "capture frame" where a momentary press makes more sense than a persistent switch.

Validation also accepts common representations: `"true"`, `"1"`, `"yes"`, `"on"`, `"false"`, `"0"`, `"no"`, `"off"`, and numbers.

### `StringConstraint`

A string, optionally with length limits and a regular expression.

```python
StringConstraint(minLength=1, maxLength=32)
StringConstraint(pattern=r"^[a-z0-9_]+$")
```

| Argument | Meaning |
| --- | --- |
| `minLength` | Minimum number of characters |
| `maxLength` | Maximum number of characters |
| `pattern` | A regular expression matched from the start of the string |

The dashboard renders a text input.

### `EnumeratedConstraint`

A fixed list of options. The dashboard renders a dropdown.

```python
EnumeratedConstraint(["largest_area", "closest_to_center"])
```

You can also include display labels:

```python
from synapse.core.settings_api import EnumeratedConstraint, EnumeratedOption

EnumeratedConstraint([
    EnumeratedOption("Largest area", "largest_area"),
    EnumeratedOption("Closest to center", "closest_to_center"),
])
```

Or build the options from an `Enum`:

```python
from enum import Enum

class Mode(Enum):
    kFast = "fast"
    kAccurate = "accurate"

mode = settingField(
    EnumeratedConstraint.fromEnum(Mode),
    default=Mode.kFast.value,
)
```

The stored value is the option value, not the display key.

### `ListConstraint`

A list value, optionally with length limits and nesting.

```python
ListConstraint(minLength=0, maxLength=10, depth=1)
```

| Argument | Meaning |
| --- | --- |
| `minLength` | Minimum number of items (`0` means no minimum) |
| `maxLength` | Maximum number of items (`0` means no maximum) |
| `depth` | Nesting depth; `2` allows a list of lists |

The dashboard renders a list editor. The constraint checks the list shape, not the type of each item.

### `ColorConstraint`

A color value, or a pair of colors when `rangeMode=True`.

```python
ColorConstraint(formatType=ColorFormat.kHex)
ColorConstraint(formatType=ColorFormat.kHSV, rangeMode=True)
```

| Format | Example |
| --- | --- |
| `ColorFormat.kHex` | `#00ff00` |
| `ColorFormat.kRGB` | `rgb(0, 255, 0)` |
| `ColorFormat.kHSV` | `hsv(60, 255, 255)` |

Use `rangeMode=True` for thresholds where a lower and upper color define a range.

### `FileConstraint`

A path to an existing file.

```python
FileConstraint(fileTypes={".onnx", ".pt"})
```

| Argument | Meaning |
| --- | --- |
| `fileTypes` | Optional set of allowed file extensions |

Validation accepts a `pathlib.Path` or a string path. A string path must exist. Relative paths are stored as absolute paths.

## Supported value types

Settings values can be:

- Integers
- Floats
- Booleans
- Strings
- Lists of the above

Bytes are supported by the settings serialization layer, but the dashboard does not provide a control for them. Use [auxiliary results](sending-results.md#auxiliary-values) for binary data.

## Camera properties

Every pipeline also exposes the camera's hardware settings through `CameraSettings`:

| Key | Constraint | Default |
| --- | --- | --- |
| `brightness` | Driver range | Camera-defined |
| `saturation` | Driver range | Camera-defined |
| `sharpness` | Driver range | Camera-defined |
| `gain` | Driver range | Camera-defined |
| `orientation` | `0`, `90`, `180`, `270` | `0` |
| `resolution` | Supported modes | `1920x1080` |

The available range and supported resolutions come from the camera driver, so they differ between cameras. Additional driver properties may appear automatically. Synapse filters out noisy or internal properties such as `raw`, `backlight`, `gamma`, and `exposure_dynamic_framerate`.

Read them with:

```python
from synapse.core.settings_api import CameraSettings

resolution = self.getCameraSetting(CameraSettings.resolution)
orientation = self.getCameraSetting(CameraSettings.orientation)
```

{% hint style="info" %}
Calibration is stored per resolution. If you change `resolution`, calibrate the camera again at the new resolution.
{% endhint %}

## Where values are saved

When you press **Save** in the dashboard, Synapse writes:

```text
config/camera_<index>/pipeline_settings.yml
config/camera_<index>/camera_configs.yml
```

Deploys preserve the remote `config/` folder, so your tuned values survive a redeploy.

## Next steps

- [Custom Pipelines](README.md)
- [Sending Results](sending-results.md)
- [Accessing Global Settings](accessing-global-settings.md)
- [Pipeline Settings (UI)](../built-in-pipelines-1/pipeline-settings.md)
