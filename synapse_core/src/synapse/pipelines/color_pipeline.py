from cv2.typing import MatLike
from synapse.core.pipeline import Pipeline
from synapse.core.settings_api import PipelineSettings
from synapse.stypes import Frame


class ColorPipeline(Pipeline):
    def __init__(self, settings: PipelineSettings, cameraIndex: int):
        self.cameraIndex = cameraIndex
        self.settings = settings

    def processFrame(self, img: MatLike, timestamp: float) -> Frame:
        return img
