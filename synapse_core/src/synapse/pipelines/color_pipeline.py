from synapse.core.pipeline import Pipeline
from synapse.core.settings_api import PipelineSettings
from synapse.stypes import CameraID, Frame


class ColorPipeline(Pipeline[PipelineSettings]):
    def __init__(self, settings: PipelineSettings):
        self.settings = settings

    def bind(self, cameraIndex: CameraID): ...

    def processFrame(self, img: Frame, timestamp: float) -> Frame:
        return img
