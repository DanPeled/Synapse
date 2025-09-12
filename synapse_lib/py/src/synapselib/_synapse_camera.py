# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from enum import Enum
from typing import Any, Final, Optional

import ntcore


class SynapseCamera:
    class NetworkTableTopics(Enum):
        kPipelineTopic = "pipeline"
        kRecordStatusTopic = "record"
        kPipelineTypeTopic = "pipeline_type"
        kResultsTopic = "results"
        kCaptureLatencyTopic = "captureLatency"
        kProcessLatencyTopic = "processLatency"
        kDataTableName = "data"
        kSettingsTableName = "settings"

    def __init__(self, cameraName: str, coprocessorName: str = "Synapse") -> None:
        self.synapseTableName: Final[str] = coprocessorName
        self.cameraName: Final[str] = cameraName

        self.__table: Final[ntcore.NetworkTable] = (
            ntcore.NetworkTableInstance.getDefault()
            .getTable(coprocessorName)
            .getSubTable(cameraName)
        )

        self.__dataTable: Optional[ntcore.NetworkTable] = None
        self.__settingsTable: Optional[ntcore.NetworkTable] = None
        self.__pipelineEntry: Optional[ntcore.NetworkTableEntry] = None
        self.__pipelineTypeEntry: Optional[ntcore.NetworkTableEntry] = None
        self.__resultsEntry: Optional[ntcore.NetworkTableEntry] = None
        self.__recordStateEntry: Optional[ntcore.NetworkTableEntry] = None
        self.__processLatencyEntry: Optional[ntcore.NetworkTableEntry] = None
        self.__captureLatencyEntry: Optional[ntcore.NetworkTableEntry] = None

    def setPipeline(self, pipeline: int) -> None:
        if self.__pipelineEntry is None:
            self.__pipelineEntry = self.__table.getEntry(
                self.NetworkTableTopics.kPipelineTopic.value
            )
        assert self.__pipelineEntry is not None
        self.__pipelineEntry.setInteger(pipeline)

    def getPipeline(self) -> int:
        if self.__pipelineEntry is None:
            self.__pipelineEntry = self.__table.getEntry(
                self.NetworkTableTopics.kPipelineTopic.value
            )
        assert self.__pipelineEntry is not None
        return self.__pipelineEntry.getInteger(-1)

    def getRecordingStatus(self) -> bool:
        if self.__recordStateEntry is None:
            self.__recordStateEntry = self.__table.getEntry(
                self.NetworkTableTopics.kRecordStatusTopic.value
            )
        assert self.__recordStateEntry is not None
        return self.__recordStateEntry.getBoolean(False)

    def setRecordingStatus(self, status: bool) -> None:
        if self.__recordStateEntry is None:
            self.__recordStateEntry = self.__table.getEntry(
                self.NetworkTableTopics.kRecordStatusTopic.value
            )
        assert self.__recordStateEntry is not None

        self.__recordStateEntry.setBoolean(status)

    def getCameraName(self) -> str:
        return self.cameraName

    def getPipelineType(self) -> str:
        if self.__pipelineTypeEntry is None:
            self.__pipelineTypeEntry = self.__table.getEntry(
                self.NetworkTableTopics.kPipelineTypeTopic.value
            )

        assert self.__pipelineTypeEntry is not None
        return self.__pipelineTypeEntry.getString("unknown")

    def getCaptureLatency(self) -> float:
        if self.__captureLatencyEntry is None:
            self.__captureLatencyEntry = self.__table.getEntry(
                self.NetworkTableTopics.kCaptureLatencyTopic.value
            )
        assert self.__captureLatencyEntry is not None
        return self.__captureLatencyEntry.getDouble(-1)

    def getProcessLatency(self) -> float:
        if self.__processLatencyEntry is None:
            self.__processLatencyEntry = self.__table.getEntry(
                self.NetworkTableTopics.kProcessLatencyTopic.value
            )
        assert self.__processLatencyEntry is not None
        return self.__processLatencyEntry.getDouble(-1)

    def getResults(self, pipeline: Any) -> Any: ...  # TODO

    def __getDataEntry(self, dataKey: str) -> ntcore.NetworkTableEntry:
        return self.__getDataRersultsTable().getEntry(dataKey)

    def __getDataRersultsTable(self) -> ntcore.NetworkTable:
        if self.__dataTable is None:
            self.__dataTable = self.__table.getSubTable(
                self.NetworkTableTopics.kDataTableName.value
            )
        assert self.__dataTable is not None

        return self.__dataTable

    def getSetting(self, key: str) -> Optional[Any]:
        entry: ntcore.NetworkTableEntry = self.__getSettingsTable().getEntry(key)
        if not entry.exists():
            return None

        entryType = entry.getType()
        if entryType == ntcore.NetworkTableType.kDouble:
            return entry.getDouble(0.0)
        elif entryType == ntcore.NetworkTableType.kDoubleArray:
            return entry.getDoubleArray([])
        elif entryType == ntcore.NetworkTableType.kString:
            return entry.getString("")
        elif entryType == ntcore.NetworkTableType.kStringArray:
            return entry.getStringArray([])
        elif entryType == ntcore.NetworkTableType.kInteger:
            return entry.getInteger(0)
        elif entryType == ntcore.NetworkTableType.kIntegerArray:
            return entry.getIntegerArray([])
        elif entryType == ntcore.NetworkTableType.kFloat:
            return entry.getFloat(0.0)
        elif entryType == ntcore.NetworkTableType.kFloatArray:
            return entry.getFloatArray([])

        return None

    def setSetting(self, key: str, value: Any) -> None:
        entry: ntcore.NetworkTableEntry = self.__getSettingsTable().getEntry(key)
        entry.setValue(value)

    def __getSettingsTable(self) -> ntcore.NetworkTable:
        if self.__settingsTable is None:
            self.__settingsTable = self.__table.getSubTable(
                self.NetworkTableTopics.kSettingsTableName.value
            )
        assert self.__settingsTable is not None
        return self.__settingsTable
