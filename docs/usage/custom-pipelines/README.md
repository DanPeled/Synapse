---
description: An intro to writing custom pipelines
---

# Custom Pipelines

While Synapse includes several built-in pipelines to get started quickly, its real power lies in its extensibility. Users can define their own custom pipelines and write code that runs directly within the runtime. This allows full control over the vision processing flow—enabling specialized logic, custom models, and unique integrations that go beyond the defaults.

In this section, we’ll walk through how to create and register your own pipeline, define processing steps, and take advantage of Synapse's runtime to execute custom logic efficiently, using a simple pipeline example that will draw a circle on the screen using OpenCV code.

{% hint style="info" %}
This is **not** a guide for how to write pipeline processing code, but how to implement a pipeline class.\
If you're looking to learn about writing vision algorithms, we recommend exploring the [OpenCV Python Examples](https://docs.opencv.org/4.x/d6/d00/tutorial_py_root.html)
{% endhint %}

## Defining the pipeline class

In order to write a custom pipeline, we need to create a python file inside of the project folder.\
Any file with the name convention `*_pipeline.py` (e.g `apriltag_pipeline.py`) will automatically be recognized as a file that _might_ have a pipeline defined inside it.&#x20;

Inside of the file, we can define a class that extends the base `Pipeline` class from the _Synapse_ library:

```python
from synapse import Pipeline, PipelineSettings
from synapse.core.pipeline import FrameResult

class MyPipeline(Pipeline):
    def __init__(self, settings: PipelineSettings):
        super().__init__(settings)
        
    def processFrame(self, img: Frame, timestamp: float) -> Frame:
        # Process loop for the pipeline, will be called every frame
        # with the image from the camera.
        # Here we can run any opencv-like code we would like.
        return img
```

This class will automatically be recognized as a valid pipeline type and will be accessable via the UI without any changes.

{% hint style="warning" %}
The <kbd>super().\_\_init\_\_(settings)</kbd>call is required in order for the pipeline to function correctly
{% endhint %}

## Defining Pipeline Settings

In order for our pipeline to have configurable settings, we will need to define a settings class, which will extend from the `PipelineSettings` class, and will be automatically validated with in-code constraints:

```python
# ... previous imports
from synapse.core.settings_api import RangeConstraint, settingField

class MyPipelineSettings(PipelineSettings):
    circle_size = settingField(RangeConstraint(minValue=0, maxValue=None), default=20)
    """Setting for the size of the circle drawn onto the screen"""

    circle_x = settingField(RangeConstraint(minValue=0, maxValue=1920), default=1920 / 2)
    circle_y = settingField(RangeConstraint(minValue=0, maxValue=1080), default=1080 / 2)
    """Position of the circle on screen, where (0, 0) is the top-left corner."""

# ...
class MyPipeline(Pipeline[MyPipelineSettings]):
    """ Now we need to make our pipeline know to use the settings class we defined """
    def __init__(self, settings: MyPipelineSettings):
        super().__init__(settings)
    
    def processFrame(self, img: Frame, timestamp: float) -> Frame:
        # Now we can access the settings we defined
        # We can do that either by using the `Setting` instance we created
        circleSize = self.getSetting(MyPipelineSettings.circle_size)
        # Or via the automatically generated key for it (same as the var name)
        circleX = self.getSetting("circle_x")
        return img
```

Now, these settings will be accessable via the UI and be validated automatically to match the constraint we gave it in-code.

{% hint style="info" %}
For detailed information about the Settings API and the available constraint types, refer to the documentation [here](settings-api.md)
{% endhint %}

## Putting it all together

Now, we can add some OpenCV code that will draw a circle on the screen for us, based on the settings we provide it in the UI:

```python
import cv2
from synapse.core.pipeline import Pipeline
from synapse.core.settings_api import PipelineSettings, settingField, RangeConstraint
from synapse.stypes import Frame


class MyPipelineSettings(PipelineSettings):
    circle_size = settingField(RangeConstraint(minValue=0, maxValue=None), default=20)
    """Setting for the size of the circle drawn onto the screen"""

    circle_x = settingField(
        RangeConstraint(minValue=0, maxValue=1920), default=1920 / 2
    )
    circle_y = settingField(
        RangeConstraint(minValue=0, maxValue=1080), default=1080 / 2
    )
    """Position of the circle on screen, where (0, 0) is the top-left corner."""


class MyPipeline(Pipeline[MyPipelineSettings]):
    def __init__(self, settings: MyPipelineSettings):
        super().__init__(settings)

    def processFrame(self, img: Frame, timestamp: float) -> Frame:
        # Get settings
        circleSize = self.getSetting(MyPipelineSettings.circle_size)
        circleX = int(self.getSetting(MyPipelineSettings.circle_x))
        circleY = int(self.getSetting(MyPipelineSettings.circle_y))

        # Draw the circle on the image
        processed = cv2.circle(
            img,  # Image to draw on
            (circleX, circleY),  # Center position
            circleSize,  # Radius
            (0, 255, 0),  # Color (green in BGR)
            thickness=2,  # Thickness of the circle edge
        )
        
        # This will provide the drawn-on frame as the frame to show on the UI
        return processed 


```

This pipeline will automatically become a valid and validated pipeline within the **UI** & **NetworkTables** without any modifications to it.&#x20;

## Pipeline Results

Coming soon...

