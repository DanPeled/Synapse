# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from enum import Enum
from typing import (Any, Final, Generic, Optional, Type, TypeVar, Union,
                    overload)

import msgpack
import ntcore

from ._deserialization import dataclass_object_hook
from .pipelines.apriltag import ApriltagResult

TResultType = TypeVar("TResultType")


class SynapsePipeline(Generic[TResultType]):
    """
    Represents a Synapse pipeline. Each pipeline is associated with a result class
    that defines the type of data returned.

    Type parameter:
        TResultType: The type of result data returned by this pipeline, typically a
        collection of results such as a list or map.
    """

    kApriltag: "SynapsePipeline['ApriltagResult']"
    """The AprilTag pipeline. This pipeline uses the `ApriltagResult` class to store the result data. """

    def __init__(self, typeref: Type[TResultType], typestring: str):
        """
        Constructor for the SynapsePipeline class.

        Args:
            typeref: The Python type associated with this pipeline's result data.
            typestring: The string identifier for this pipeline (topic name).
        """
        self._typeref: Type[TResultType] = typeref
        self.typestring: str = typestring

    @property
    def typeref(self) -> Type[TResultType]:
        """
        Gets the Python type reference for this pipeline.

        Returns:
            The Python type representing the result type (TResultType).
        """
        return self._typeref

    def __eq__(self, other: object) -> bool:
        """
        Compares this SynapsePipeline with another object for equality.

        Two pipelines are considered equal if both their `typeref` and `typestring`
        are equal.
        """
        if not isinstance(other, SynapsePipeline):
            return False
        return self._typeref == other._typeref and self.typestring == other.typestring

    def __hash__(self) -> int:
        """
        Computes a hash code for this SynapsePipeline.

        The hash code is based on the same fields used in equality:
        `typeref` and `typestring`.
        """
        return hash((self._typeref, self.typestring))


SynapsePipeline.kApriltag = SynapsePipeline(ApriltagResult, "ApriltagPipeline")


class SynapseCamera:
    """
    Represents a camera in the Synapse system, providing methods to manage settings
    and retrieve results from NetworkTables.
    """

    class NetworkTableTopics(Enum):
        """
        Standard NetworkTables topic keys used for communication between Synapse
        and coprocessors.
        """

        kPipelineTopic = "pipeline"
        kRecordStatusTopic = "record"
        kPipelineTypeTopic = "pipeline_type"
        kResultsTopic = "results"
        kCaptureLatencyTopic = "captureLatency"
        kProcessLatencyTopic = "processLatency"
        kDataTableName = "data"
        kSettingsTableName = "settings"

    def __init__(self, cameraName: str, coprocessorName: str = "Synapse") -> None:
        """
        Constructs a new SynapseCamera instance.

        Args:
            cameraName: The camera's name.
            coprocessorName: The coprocessor table name (default: "Synapse").
        """
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
        """Sets the camera pipeline ID."""
        if self.__pipelineEntry is None:
            self.__pipelineEntry = self.__table.getEntry(
                self.NetworkTableTopics.kPipelineTopic.value
            )
        assert self.__pipelineEntry is not None
        self.__pipelineEntry.setInteger(pipeline)

    def getPipeline(self) -> int:
        """Gets the current pipeline ID. Returns -1 if not set."""
        if self.__pipelineEntry is None:
            self.__pipelineEntry = self.__table.getEntry(
                self.NetworkTableTopics.kPipelineTopic.value
            )
        assert self.__pipelineEntry is not None
        return self.__pipelineEntry.getInteger(-1)

    def getRecordingStatus(self) -> bool:
        """Gets the current recording status of the camera."""
        if self.__recordStateEntry is None:
            self.__recordStateEntry = self.__table.getEntry(
                self.NetworkTableTopics.kRecordStatusTopic.value
            )
        assert self.__recordStateEntry is not None
        return self.__recordStateEntry.getBoolean(False)

    def setRecordingStatus(self, status: bool) -> None:
        """Sets the recording status of the camera."""
        if self.__recordStateEntry is None:
            self.__recordStateEntry = self.__table.getEntry(
                self.NetworkTableTopics.kRecordStatusTopic.value
            )
        assert self.__recordStateEntry is not None
        self.__recordStateEntry.setBoolean(status)

    def getCameraName(self) -> str:
        """Retrieves the camera name."""
        return self.cameraName

    def getPipelineType(self) -> str:
        """Gets the pipeline type string from the camera. Returns 'unknown' if not set."""
        if self.__pipelineTypeEntry is None:
            self.__pipelineTypeEntry = self.__table.getEntry(
                self.NetworkTableTopics.kPipelineTypeTopic.value
            )
        assert self.__pipelineTypeEntry is not None
        return self.__pipelineTypeEntry.getString("unknown")

    def getCaptureLatency(self) -> float:
        """Gets the latest capture latency from the camera in milliseconds."""
        if self.__captureLatencyEntry is None:
            self.__captureLatencyEntry = self.__table.getEntry(
                self.NetworkTableTopics.kCaptureLatencyTopic.value
            )
        assert self.__captureLatencyEntry is not None
        return self.__captureLatencyEntry.getDouble(-1)

    def getProcessLatency(self) -> float:
        """Gets the latest processing latency from the camera in milliseconds."""
        if self.__processLatencyEntry is None:
            self.__processLatencyEntry = self.__table.getEntry(
                self.NetworkTableTopics.kProcessLatencyTopic.value
            )
        assert self.__processLatencyEntry is not None
        return self.__processLatencyEntry.getDouble(-1)

    @overload
    def getResults(self, t: Type[TResultType]) -> TResultType:
        """
        Fetches and deserializes the camera's results as a specific type.

        Args:
            t: The class type representing the expected result.

        Returns:
            An instance of TResultType deserialized from the camera's data.

        Raises:
            AssertionError: If the pipeline type does not match the currently active pipeline.
        """
        ...

    @overload
    def getResults(self, t: SynapsePipeline[TResultType]) -> TResultType:
        """
        Fetches and deserializes the camera's results for a given SynapsePipeline.

        Args:
            t: A SynapsePipeline object representing the pipeline whose results to fetch.

        Returns:
            An instance of TResultType deserialized from the pipeline's results.
        """
        ...

    def getResults(
        self, t: Union[Type[TResultType], SynapsePipeline[TResultType]]
    ) -> TResultType:
        if isinstance(t, SynapsePipeline):
            assert self.getPipelineType() == t.typestring

        typeref = t.typeref if isinstance(t, SynapsePipeline) else t

        return msgpack.unpackb(
            self.__getDataEntry(self.NetworkTableTopics.kResultsTopic.value).getRaw(
                msgpack.packb({})
            ),
            raw=False,
            object_hook=dataclass_object_hook(typeref),
        )

    def __getDataEntry(self, dataKey: str) -> ntcore.NetworkTableEntry:
        """Retrieves a specific entry from the camera's data table."""
        return self.__getDataResultsTable().getEntry(dataKey)

    def __getDataResultsTable(self) -> ntcore.NetworkTable:
        """Retrieves the data table for this camera."""
        if self.__dataTable is None:
            self.__dataTable = self.__table.getSubTable(
                self.NetworkTableTopics.kDataTableName.value
            )
        assert self.__dataTable is not None
        return self.__dataTable

    def getSetting(self, key: str) -> Optional[Any]:
        """Retrieves a camera setting value from the settings table."""
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
        """Sets a camera setting value in the settings table."""
        entry: ntcore.NetworkTableEntry = self.__getSettingsTable().getEntry(key)
        entry.setValue(value)

    def __getSettingsTable(self) -> ntcore.NetworkTable:
        """Retrieves the settings table for this camera."""
        if self.__settingsTable is None:
            self.__settingsTable = self.__table.getSubTable(
                self.NetworkTableTopics.kSettingsTableName.value
            )
        assert self.__settingsTable is not None
        return self.__settingsTable
