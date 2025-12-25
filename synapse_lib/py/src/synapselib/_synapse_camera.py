# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import Dict, Generic, Optional, Type, TypeVar, cast

import msgpack
from ntcore import (NetworkTable, NetworkTableEntry, NetworkTableInstance,
                    NetworkTableType)

from ._deserialization import dataclass_object_hook
from .pipelines.apriltag import ApriltagResult
from .pipelines.color import ColorResult

T = TypeVar("T")


TPipelineResult = TypeVar("TPipelineResult")


class SynapsePipelineType(Generic[TPipelineResult]):
    """
    Represents a Synapse pipeline. Each pipeline is associated with a result class that defines the
    type of data returned.

    :param T: the type of result data returned by this pipeline, typically a dataclass or list of results
    """

    # -----------------------------
    # Predefined pipelines
    # -----------------------------
    kApriltag: SynapsePipelineType[ApriltagResult]
    kColor: SynapsePipelineType[ColorResult]

    def __init__(self, resultType: Type[TPipelineResult], typestring: str) -> None:
        """
        Constructor for the SynapsePipelineType class.

        :param resultType: The class associated with this pipeline's result data
        :param typestring: The string identifier for this pipeline
        """
        self._resultType: Type[TPipelineResult] = resultType
        self.typestring: str = typestring

    # -----------------------------
    # Accessors
    # -----------------------------
    def getResultType(self) -> Type[TPipelineResult]:
        """
        Gets the result type for this pipeline.

        :return: The class representing the result type T
        """
        return self._resultType


# Define the static pipelines
SynapsePipelineType.kApriltag = SynapsePipelineType(ApriltagResult, "ApriltagPipeline")
SynapsePipelineType.kColor = SynapsePipelineType(ColorResult, "ColorPipeline")


class SynapseCamera:
    """
    Represents a Synapse camera with fully cached NetworkTables entries, type-safe settings,
    and methods for retrieving results and metrics.
    """

    # ---------------------------------------
    # Construction
    # ---------------------------------------

    def __init__(self, cameraName: str, coprocessorName: str = "Synapse") -> None:
        """
        Constructs a new SynapseCamera with a specific coprocessor table name.

        :param cameraName: the camera's name
        :param coprocessorName: the NetworkTables root table for this camera
        """
        self.cameraName: str = cameraName
        self.synapseTableName: str = coprocessorName

        self.table: Optional[NetworkTable] = None
        self.settingsTable: Optional[NetworkTable] = None
        self.dataTable: Optional[NetworkTable] = None

        self.entryCache: Dict[str, NetworkTableEntry] = {}

        self.pipelineEntry: Optional[NetworkTableEntry] = None
        self.pipelineTypeEntry: Optional[NetworkTableEntry] = None
        self.resultsEntry: Optional[NetworkTableEntry] = None
        self.recordStateEntry: Optional[NetworkTableEntry] = None
        self.captureLatencyEntry: Optional[NetworkTableEntry] = None
        self.processLatencyEntry: Optional[NetworkTableEntry] = None

        inst = NetworkTableInstance.getDefault()
        self.table = inst.getTable(self.synapseTableName).getSubTable(self.cameraName)

    # ---------------------------------------
    # Topics
    # ---------------------------------------

    class NetworkTableTopics:
        """
        Standardized NetworkTables topic keys for pipelines, results, recording, and latency.
        """

        kPipelineTopic = "pipeline"
        kRecordStatusTopic = "record"
        kPipelineTypeTopic = "pipeline_type"
        kResultsTopic = "results"
        kCaptureLatencyTopic = "captureLatency"
        kProcessLatencyTopic = "processLatency"

    # ---------------------------------------
    # Subtables
    # ---------------------------------------

    def getSettingsTable(self) -> NetworkTable:
        """
        Returns the settings subtable.

        :return: the NetworkTable storing camera settings
        """
        assert self.table is not None
        if self.settingsTable is None:
            self.settingsTable = self.table.getSubTable("settings")
        return self.settingsTable

    def getDataTable(self) -> NetworkTable:
        """
        Returns the data/results subtable.

        :return: the NetworkTable storing camera results
        """
        assert self.table is not None
        if self.dataTable is None:
            self.dataTable = self.table.getSubTable("data")
        return self.dataTable

    # ---------------------------------------
    # Entry caching
    # ---------------------------------------

    def getCachedEntry(
        self, key: str, table: Optional[NetworkTable]
    ) -> NetworkTableEntry:
        """
        Retrieves a cached NetworkTableEntry for a given key.

        :param key: the entry key
        :param table: the table to fetch the entry from
        :return: the cached or newly fetched NetworkTableEntry
        """

        assert table is not None
        if key not in self.entryCache:
            self.entryCache[key] = table.getEntry(key)
        return self.entryCache[key]

    # ---------------------------------------
    # Pipeline getters / setters
    # ---------------------------------------

    def getPipeline(self) -> int:
        """
        Returns the current pipeline ID or -1 if unset.

        :return: the pipeline index
        """
        if self.pipelineEntry is None:
            self.pipelineEntry = self.getCachedEntry(
                self.NetworkTableTopics.kPipelineTopic, self.table
            )
        return self.pipelineEntry.getInteger(-1)

    def setPipeline(self, pipeline: int) -> None:
        """
        Sets the current pipeline ID.

        :param pipeline: pipeline index
        """
        if self.pipelineEntry is None:
            self.pipelineEntry = self.getCachedEntry(
                self.NetworkTableTopics.kPipelineTopic, self.table
            )
        self.pipelineEntry.setInteger(pipeline)

    # ---------------------------------------
    # Pipeline type string
    # ---------------------------------------

    def getPipelineType(self) -> str:
        """
        Returns the pipeline type string.

        :return: the pipeline type
        """
        if self.pipelineTypeEntry is None:
            self.pipelineTypeEntry = self.getCachedEntry(
                self.NetworkTableTopics.kPipelineTypeTopic, self.table
            )
        return self.pipelineTypeEntry.getString("unknown")

    # ---------------------------------------
    # Recording
    # ---------------------------------------

    def getRecordingStatus(self) -> bool:
        """
        Returns whether the camera is currently recording.

        :return: true if recording, false otherwise
        """
        if self.recordStateEntry is None:
            self.recordStateEntry = self.getCachedEntry(
                self.NetworkTableTopics.kRecordStatusTopic, self.table
            )
        return self.recordStateEntry.getBoolean(False)

    def setRecordStatus(self, status: bool) -> None:
        """
        Sets the camera recording status.

        :param status: true to start recording, false to stop
        """
        if self.recordStateEntry is None:
            self.recordStateEntry = self.getCachedEntry(
                self.NetworkTableTopics.kRecordStatusTopic, self.table
            )
        self.recordStateEntry.setBoolean(status)

    # ---------------------------------------
    # Latencies
    # ---------------------------------------

    def getCaptureLatency(self) -> float:
        """
        Returns the latest capture latency in milliseconds.

        :return: capture latency
        """
        if self.captureLatencyEntry is None:
            self.captureLatencyEntry = self.getCachedEntry(
                self.NetworkTableTopics.kCaptureLatencyTopic, self.table
            )
        return self.captureLatencyEntry.getDouble(-1)

    def getProcessLatency(self) -> float:
        """
        Returns the latest processing latency in milliseconds.

        :return: processing latency
        """
        if self.processLatencyEntry is None:
            self.processLatencyEntry = self.getCachedEntry(
                self.NetworkTableTopics.kProcessLatencyTopic, self.table
            )
        return self.processLatencyEntry.getDouble(-1)

    # ---------------------------------------
    # Untyped deprecated setting getter
    # ---------------------------------------

    def getSettingDeprecated(self, key: str) -> Optional[object]:
        """
        Deprecated untyped setting retrieval.

        :param key: the setting key
        :return: Optional containing the value if present
        """
        entry = self.getCachedEntry(key, self.getSettingsTable())

        t = entry.getType()

        if t == NetworkTableType.kDouble:
            return entry.getDouble(0.0)
        if t == NetworkTableType.kString:
            return entry.getString("")
        if t == NetworkTableType.kBoolean:
            return entry.getBoolean(False)
        if t == NetworkTableType.kInteger:
            return entry.getInteger(0)
        if t == NetworkTableType.kDoubleArray:
            return entry.getDoubleArray([])
        if t == NetworkTableType.kStringArray:
            return entry.getStringArray([])
        if t == NetworkTableType.kBooleanArray:
            return entry.getBooleanArray([])

        return None

    # ---------------------------------------
    # Typed settings
    # ---------------------------------------

    def getSetting(self, setting: "Setting[T]") -> Optional[T]:
        """
        Typed getter for camera settings.

        :param setting: the typed setting
        :param <T>: the value type
        :return: Optional containing value if present and type matches
        """
        entry = self.getCachedEntry(setting.key, self.getSettingsTable())

        if entry.getType() != setting.ntType:
            return None

        if entry.getType() == NetworkTableType.kDouble:
            val = entry.getDouble(0.0)
        elif entry.getType() == NetworkTableType.kInteger:
            val = entry.getInteger(0)
        elif entry.getType() == NetworkTableType.kString:
            val = entry.getString("")
        elif entry.getType() == NetworkTableType.kBoolean:
            val = entry.getBoolean(False)
        elif entry.getType() == NetworkTableType.kDoubleArray:
            val = entry.getDoubleArray([])
        elif entry.getType() == NetworkTableType.kStringArray:
            val = entry.getStringArray([])
        elif entry.getType() == NetworkTableType.kBooleanArray:
            val = entry.getBooleanArray([])
        else:
            return None

        if isinstance(val, setting.valueType):
            return val
        return None

    def setSetting(self, setting: "Setting[T]", value: T) -> None:
        """
        Typed setter for camera settings.

        :param setting: the typed setting
        :param value: the value to set
        :param <T>: type of the value
        :raises TypeError: if the value type does not match the expected NetworkTableType
        """
        entry = self.getCachedEntry(setting.key, self.getSettingsTable())

        if setting.ntType == NetworkTableType.kDouble:
            entry.setDouble(float(value))  # pyright: ignore
        elif setting.ntType == NetworkTableType.kInteger:
            entry.setInteger(int(value))  # pyright: ignore
        elif setting.ntType == NetworkTableType.kString:
            entry.setString(str(value))
        elif setting.ntType == NetworkTableType.kBoolean:
            entry.setBoolean(bool(value))
        elif setting.ntType == NetworkTableType.kDoubleArray:
            entry.setDoubleArray(value)  # type: ignore
        elif setting.ntType == NetworkTableType.kStringArray:
            entry.setStringArray(value)  # type: ignore
        elif setting.ntType == NetworkTableType.kBooleanArray:
            entry.setBooleanArray(value)  # type: ignore
        else:
            raise TypeError(f"Unsupported NT type for setting '{setting.key}'")

    # ---------------------------------------
    # Results
    # ---------------------------------------

    def getResultsEntry(self) -> NetworkTableEntry:
        """
        Returns the results entry.

        :return: cached results NetworkTableEntry
        """
        if self.resultsEntry is None:
            self.resultsEntry = self.getCachedEntry(
                self.NetworkTableTopics.kResultsTopic, self.getDataTable()
            )
        return self.resultsEntry

    def getResults(self, resultType: Type[T], data: bytes) -> Optional[T]:
        """
        Deserialize results from serialized MessagePack data into the given dataclass type.

        :param resultType: type of the result (dataclass)
        :param data: serialized MessagePack bytes
        :return: Optional containing deserialized results
        """
        if not data:
            return None

        try:
            result = msgpack.loads(
                data, raw=False, object_hook=dataclass_object_hook(resultType)
            )
            return cast(Optional[T], result)
        except Exception as e:
            print(f"[SynapseCamera] Failed to decode results: {e}")
            return None

    # ---------------------------------------
    # Name
    # ---------------------------------------

    def getCameraName(self) -> str:
        """
        Returns the camera name.

        :return: camera name
        """
        return self.cameraName


class Setting(Generic[T]):
    """
    Represents a typed Synapse setting that can be stored in a NetworkTable.

    :param <T>: The type of the setting value (e.g., Double, String, arrays, etc.)
    """

    key: str
    valueType: Type[T]
    ntType: NetworkTableType

    def __init__(self, key: str, valueType: Type[T], ntType: NetworkTableType):
        self.key = key
        self.valueType = valueType
        self.ntType = ntType

    kBrightness: Setting[float]
    kGain: Setting[float]
    kExposure: Setting[float]
    kOrientation: Setting[int]

    @staticmethod
    def doubleSetting(key: str) -> "Setting[float]":
        return Setting(key, float, NetworkTableType.kDouble)

    @staticmethod
    def integerSetting(key: str) -> "Setting[int]":
        return Setting(key, int, NetworkTableType.kInteger)

    @staticmethod
    def stringSetting(key: str) -> "Setting[str]":
        return Setting(key, str, NetworkTableType.kString)

    @staticmethod
    def doubleArraySetting(key: str) -> "Setting[list[float]]":
        return Setting(key, list, NetworkTableType.kDoubleArray)

    @staticmethod
    def stringArraySetting(key: str) -> "Setting[list[str]]":
        return Setting(key, list, NetworkTableType.kStringArray)

    @staticmethod
    def booleanSetting(key: str) -> "Setting[bool]":
        return Setting(key, bool, NetworkTableType.kBoolean)


Setting.kBrightness = Setting.doubleSetting("brightness")
Setting.kGain = Setting.doubleSetting("gain")
Setting.kExposure = Setting.doubleSetting("exposure")
Setting.kOrientation = Setting.integerSetting("orientation")
