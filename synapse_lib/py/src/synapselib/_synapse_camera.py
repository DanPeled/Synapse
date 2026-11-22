# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import warnings
from typing import Any, Dict, Generic, Optional, Set, Type, TypeVar, cast

import msgpack
from ntcore import (
    BooleanSubscriber,
    DoubleSubscriber,
    GenericSubscriber,
    IntegerSubscriber,
    NetworkTable,
    NetworkTableEntry,
    NetworkTableInstance,
    NetworkTableType,
    RawSubscriber,
    StringSubscriber,
    Value,
)

from ._deserialization import from_dict
from ._generated import topics as _topics
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
SynapsePipelineType.kApriltag = SynapsePipelineType(
    ApriltagResult, _topics.APRILTAG_PIPELINE
)
SynapsePipelineType.kColor = SynapsePipelineType(ColorResult, _topics.COLOR_PIPELINE)


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
        self.settingSubscribers: Dict[str, GenericSubscriber] = {}
        self.warnedSettingKeys: Set[str] = set()

        self.pipelineEntry: Optional[NetworkTableEntry] = None
        self.pipelineSubscriber: Optional[IntegerSubscriber] = None
        self.pipelineTypeEntry: Optional[NetworkTableEntry] = None
        self.pipelineTypeSubscriber: Optional[StringSubscriber] = None
        self.resultsEntry: Optional[NetworkTableEntry] = None
        self.resultsSubscriber: Optional[RawSubscriber] = None
        self.recordStateEntry: Optional[NetworkTableEntry] = None
        self.recordStateSubscriber: Optional[BooleanSubscriber] = None
        self.captureLatencyEntry: Optional[NetworkTableEntry] = None
        self.captureLatencySubscriber: Optional[DoubleSubscriber] = None
        self.processLatencyEntry: Optional[NetworkTableEntry] = None
        self.processLatencySubscriber: Optional[DoubleSubscriber] = None

        inst = NetworkTableInstance.getDefault()
        self.table = inst.getTable(self.synapseTableName).getSubTable(self.cameraName)

    # ---------------------------------------
    # Topics
    # ---------------------------------------

    class NetworkTableTopics:
        """
        Standardized NetworkTables topic keys for pipelines, results, recording, and latency.
        """

        kPipelineTopic = _topics.PIPELINE
        kRecordStatusTopic = _topics.RECORD
        kPipelineTypeTopic = _topics.PIPELINE_TYPE
        kResultsTopic = _topics.RESULTS
        kViewIDTopic = _topics.VIEW_ID
        kCaptureLatencyTopic = _topics.CAPTURE_LATENCY
        kProcessLatencyTopic = _topics.PROCESS_LATENCY

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
            self.settingsTable = self.table.getSubTable(_topics.SETTINGS_TABLE)
        return self.settingsTable

    def getDataTable(self) -> NetworkTable:
        """
        Returns the data/results subtable.

        :return: the NetworkTable storing camera results
        """
        assert self.table is not None
        if self.dataTable is None:
            self.dataTable = self.table.getSubTable(_topics.DATA_TABLE)
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
        cache_key = self._cacheKey(table, key)
        if cache_key not in self.entryCache:
            self.entryCache[cache_key] = table.getEntry(key)
        return self.entryCache[cache_key]

    def getSettingSubscriber(
        self, key: str, table: Optional[NetworkTable]
    ) -> GenericSubscriber:
        """
        Returns a cached latest-value subscriber for a setting topic.

        :param key: the setting key
        :param table: the table that owns the setting
        :return: the cached or newly created generic subscriber
        """

        assert table is not None
        cache_key = self._cacheKey(table, key)
        if cache_key not in self.settingSubscribers:
            self.settingSubscribers[cache_key] = table.getTopic(key).genericSubscribe()
        return self.settingSubscribers[cache_key]

    @staticmethod
    def _cacheKey(table: NetworkTable, key: str) -> str:
        """Builds a cache key from the full NetworkTables topic path."""

        return f"{table.getPath()}/{key}"

    @staticmethod
    def _valueToObject(value: Value) -> Optional[object]:
        """Converts an NT value to the Python type used by :class:`Setting`."""

        if value.isDouble():
            return value.getDouble()
        if value.isInteger():
            return value.getInteger()
        if value.isString():
            return value.getString()
        if value.isBoolean():
            return value.getBoolean()
        if value.isDoubleArray():
            return value.getDoubleArray()
        if value.isIntegerArray():
            return value.getIntegerArray()
        if value.isStringArray():
            return value.getStringArray()
        if value.isBooleanArray():
            return value.getBooleanArray()
        return None

    def _warnMismatchOnce(
        self,
        setting: "Setting[Any]",
        actualType: NetworkTableType,
        value: Optional[object],
    ) -> None:
        """Reports a setting type mismatch only once per full topic path."""

        warningKey = self._cacheKey(self.getSettingsTable(), setting.key)
        if warningKey in self.warnedSettingKeys:
            return
        self.warnedSettingKeys.add(warningKey)
        warnings.warn(
            f"[SynapseCamera] Type mismatch for key '{setting.key}', expected "
            f"{setting.ntType} ({setting.valueType.__name__}) but received "
            f"{actualType} ({type(value).__name__})",
            RuntimeWarning,
            stacklevel=2,
        )

    # ---------------------------------------
    # Pipeline getters / setters
    # ---------------------------------------

    def getPipeline(self) -> int:
        """
        Returns the current pipeline ID or -1 if unset.

        :return: the pipeline index
        """
        if self.pipelineSubscriber is None:
            assert self.table is not None
            self.pipelineSubscriber = self.table.getIntegerTopic(
                self.NetworkTableTopics.kPipelineTopic
            ).subscribe(-1)
        return self.pipelineSubscriber.get()

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
        if self.pipelineTypeSubscriber is None:
            assert self.table is not None
            self.pipelineTypeSubscriber = self.table.getStringTopic(
                self.NetworkTableTopics.kPipelineTypeTopic
            ).subscribe("unknown")
        return self.pipelineTypeSubscriber.get()

    # ---------------------------------------
    # Recording
    # ---------------------------------------

    def getRecordingStatus(self) -> bool:
        """
        Returns whether the camera is currently recording.

        :return: true if recording, false otherwise
        """
        if self.recordStateSubscriber is None:
            assert self.table is not None
            self.recordStateSubscriber = self.table.getBooleanTopic(
                self.NetworkTableTopics.kRecordStatusTopic
            ).subscribe(False)
        return self.recordStateSubscriber.get()

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
        Returns the latest capture latency in seconds.

        :return: capture latency in seconds, or 0.0 if it has not been published
        """
        if self.captureLatencySubscriber is None:
            assert self.table is not None
            self.captureLatencySubscriber = self.table.getDoubleTopic(
                self.NetworkTableTopics.kCaptureLatencyTopic
            ).subscribe(0.0)
        return self.captureLatencySubscriber.get()

    def getProcessLatency(self) -> float:
        """
        Returns the latest processing latency in seconds.

        :return: processing latency in seconds, or 0.0 if it has not been published
        """
        if self.processLatencySubscriber is None:
            assert self.table is not None
            self.processLatencySubscriber = self.table.getDoubleTopic(
                self.NetworkTableTopics.kProcessLatencyTopic
            ).subscribe(0.0)
        return self.processLatencySubscriber.get()

    # ---------------------------------------
    # Untyped deprecated setting getter
    # ---------------------------------------

    def getSettingDeprecated(self, key: str) -> Optional[object]:
        """
        Deprecated untyped setting retrieval.

        :param key: the setting key
        :return: Optional containing the value if present
        """
        value = self.getSettingSubscriber(key, self.getSettingsTable()).get()
        if not value.isValid():
            return None
        return self._valueToObject(value)

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
        value = self.getSettingSubscriber(setting.key, self.getSettingsTable()).get()
        if not value.isValid():
            return None

        converted = self._valueToObject(value)
        if converted is None or value.type() != setting.ntType:
            self._warnMismatchOnce(setting, value.type(), converted)
            return None

        if not isinstance(converted, setting.valueType):
            self._warnMismatchOnce(setting, value.type(), converted)
            return None

        return cast(T, converted)

    def setSetting(self, setting: "Setting[T]", value: T) -> None:
        """
        Typed setter for camera settings.

        :param setting: the typed setting
        :param value: the value to set
        :param <T>: type of the value
        :raises TypeError: if the value type does not match the expected NetworkTableType
        """
        entry = self.getCachedEntry(setting.key, self.getSettingsTable())

        if setting.ntType == NetworkTableType.DOUBLE:
            entry.setDouble(float(value))  # pyright: ignore
        elif setting.ntType == NetworkTableType.INTEGER:
            entry.setInteger(int(value))  # pyright: ignore
        elif setting.ntType == NetworkTableType.STRING:
            entry.setString(str(value))
        elif setting.ntType == NetworkTableType.BOOLEAN:
            entry.setBoolean(bool(value))
        elif setting.ntType == NetworkTableType.DOUBLE_ARRAY:
            entry.setDoubleArray(value)  # type: ignore
        elif setting.ntType == NetworkTableType.STRING_ARRAY:
            entry.setStringArray(value)  # type: ignore
        elif setting.ntType == NetworkTableType.BOOLEAN_ARRAY:
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
            payload = cast(Dict[str, Any], msgpack.loads(data, raw=False))
            return cast(T, from_dict(resultType, payload))
        except Exception as e:
            print(f"[SynapseCamera] Failed to decode results: {e}")
            return None

    def getLatestResults(self, pipelineType: "SynapsePipelineType[T]") -> Optional[T]:
        """
        Read and deserialize the latest results for a pipeline from NetworkTables.

        Results are published under ``<camera>/data/results`` as MessagePack.

        :param pipelineType: the pipeline type whose results should be decoded
        :return: the latest decoded results, or ``None`` when no results are available
        """
        if self.resultsSubscriber is None:
            assert self.table is not None
            self.resultsSubscriber = (
                self.getDataTable()
                .getRawTopic(self.NetworkTableTopics.kResultsTopic)
                .subscribe("raw", b"")
            )
        data = self.resultsSubscriber.get()
        return self.getResults(pipelineType.getResultType(), data)

    # ---------------------------------------
    # Cleanup
    # ---------------------------------------

    def close(self) -> None:
        """Closes the typed latest-value subscribers owned by this camera."""

        for subscriber in (
            self.pipelineSubscriber,
            self.pipelineTypeSubscriber,
            self.recordStateSubscriber,
            self.captureLatencySubscriber,
            self.processLatencySubscriber,
            self.resultsSubscriber,
        ):
            if subscriber is not None:
                subscriber.close()
        self.settingSubscribers.clear()
        self.warnedSettingKeys.clear()

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
    kContrast: Setting[float]
    kSaturation: Setting[float]
    kHue: Setting[float]
    kWhiteBalanceTemperature: Setting[float]
    kSharpness: Setting[float]

    @staticmethod
    def doubleSetting(key: str) -> "Setting[float]":
        return Setting(key, float, NetworkTableType.DOUBLE)

    @staticmethod
    def integerSetting(key: str) -> "Setting[int]":
        return Setting(key, int, NetworkTableType.INTEGER)

    @staticmethod
    def stringSetting(key: str) -> "Setting[str]":
        return Setting(key, str, NetworkTableType.STRING)

    @staticmethod
    def doubleArraySetting(key: str) -> "Setting[list[float]]":
        return Setting(key, list, NetworkTableType.DOUBLE_ARRAY)

    @staticmethod
    def stringArraySetting(key: str) -> "Setting[list[str]]":
        return Setting(key, list, NetworkTableType.STRING_ARRAY)

    @staticmethod
    def booleanSetting(key: str) -> "Setting[bool]":
        return Setting(key, bool, NetworkTableType.BOOLEAN)


Setting.kBrightness = Setting.doubleSetting(_topics.BRIGHTNESS_SETTING)
Setting.kGain = Setting.doubleSetting(_topics.GAIN_SETTING)
Setting.kExposure = Setting.doubleSetting(_topics.EXPOSURE_SETTING)
Setting.kOrientation = Setting.integerSetting(_topics.ORIENTATION_SETTING)
Setting.kContrast = Setting.doubleSetting(_topics.CONTRAST_SETTING)
Setting.kSaturation = Setting.doubleSetting(_topics.SATURATION_SETTING)
Setting.kHue = Setting.doubleSetting(_topics.HUE_SETTING)
Setting.kWhiteBalanceTemperature = Setting.doubleSetting(
    _topics.WHITE_BALANCE_TEMPERATURE_SETTING
)
Setting.kSharpness = Setting.doubleSetting(_topics.SHARPNESS_SETTING)
