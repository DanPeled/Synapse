# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from synapse.core.pipeline import Pipeline, PipelineResult
from synapse.core.settings_api import PipelineSettings
from synapse.stypes import Frame


class ColorPipeline(Pipeline[PipelineSettings, PipelineResult]):
    def __init__(self, settings: PipelineSettings):
        super().__init__(settings)
        self.settings = settings

    def processFrame(self, img: Frame, timestamp: float) -> Frame:
        return img
