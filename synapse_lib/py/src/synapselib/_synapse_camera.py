# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from enum import Enum
from typing import Final

import ntcore


class SynapseCamera:
    class NetworkTableTopics(Enum):
        kPipelineTopic = "pipeline"
        kRecordStatusTopic = "record"
        kPipelineTypeTopic = "pipeline_type"
        kResultsTopic = "results"
        kCaptureLatencyTopic = "captureLatency"
        kProcessLatencyTopic = "processLatency"

    def __init__(self, cameraName: str, coprocessorName: str = "Synapse") -> None:
        self.synapseTableName: Final[str] = coprocessorName
        self.cameraName: Final[str] = cameraName

        self.__table: Final[ntcore.NetworkTable] = (
            ntcore.NetworkTableInstance.getDefault()
            .getTable(coprocessorName)
            .getSubTable(cameraName)
        )
        self.__dataTable: ntcore.NetworkTable
