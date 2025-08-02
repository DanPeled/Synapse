# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from synapse.core.pipeline import Pipeline
from synapse.core.settings_api import PipelineSettings
from synapse.stypes import CameraID, Frame


class ColorPipeline(Pipeline[PipelineSettings]):
    def __init__(self, settings: PipelineSettings):
        super().__init__(settings)
        self.settings = settings

    def bind(self, cameraIndex: CameraID): ...

    def processFrame(self, img: Frame, timestamp: float) -> Frame:
        return img
