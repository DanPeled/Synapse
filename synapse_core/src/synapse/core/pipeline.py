# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache
from typing import (Any, Callable, Dict, Generic, Iterable, List, Optional,
                    Type, TypeVar, Union, overload)

from ntcore import NetworkTable, NetworkTableEntry
from synapse_net.proto.v1 import (MessageTypeProto, PipelineProto,
                                  PipelineResultProto)
from synapse_net.socketServer import WebSocketServer

from ..log import createMessage, err
from ..stypes import CameraID, Frame, PipelineID
from .camera_factory import SynapseCamera
from .global_settings import GlobalSettings
from .results_api import (PipelineResult, parsePipelineResult,
                          serializePipelineResult)
from .settings_api import (CameraSettings, PipelineSettings, Setting,
                           SettingsAPI, SettingsValue, TConstraintType,
                           TSettingValueType, settingValueToProto)

FrameResult = Optional[Frame]


def isFrameResult(value: object) -> bool:
    """Check if value is a FrameResult (Frame, iterable of Frames, or None)."""
    if value is None or isinstance(value, Frame):
        return True
    if isinstance(value, Iterable):
        for f in value:
            if not isinstance(f, Frame):
                return False
        return True
    return False


TSettingsType = TypeVar("TSettingsType", bound=PipelineSettings)
TResultType = TypeVar("TResultType", bound=PipelineResult)

PipelineProcessFrameResult = FrameResult

DataTableKey = "data"
ResultsTopicKey = "results"


class Pipeline(ABC, Generic[TSettingsType, TResultType]):
    """
    Base class for vision pipelines with NT publishing, camera binding, and settings support.
    """

    __is_enabled__ = True
    VALID_ENTRY_TYPES = Any
    ntTable: Optional[NetworkTable] = None

    _ntDataTable: Optional[NetworkTable]
    _ntEntries: Dict[str, NetworkTableEntry]

    @abstractmethod
    def __init__(self, settings: TSettingsType):
        """
        Initialize the pipeline with settings.
        """
        self.settings: TSettingsType = settings
        self.cameraSettings: Dict[CameraID, CameraSettings] = {}
        self.cameraIndex: CameraID = -1
        self.pipelineIndex: PipelineID = -1
        self.name: str = "new pipeline"

        # NT caching
        self._ntDataTable = None
        self._ntEntries = {}

    def bind(self, cameraIndex: CameraID, camera: SynapseCamera):
        """
        Bind a camera to this pipeline and reset cached NT entries for type safety.
        """
        self.invalidateCachedEntries()
        self.cameraIndex = cameraIndex

        if cameraIndex not in self.cameraSettings:
            self.cameraSettings[cameraIndex] = CameraSettings()
        self.cameraSettings[cameraIndex].fromCamera(camera)

    @abstractmethod
    def processFrame(self, img, timestamp: float) -> PipelineProcessFrameResult:
        """
        Process a single frame. Must be implemented by subclasses.
        """
        pass

    def preProcessCleanup(self) -> None:
        """
        Cleanup before processing a new frame.
        Resets results and invalidates NT cache.
        """
        self.setResults(None)
        # self.invalidateCachedEntries()

    def invalidateCachedEntries(self) -> None:
        """
        Clear all cached NT entries to allow new types after pipeline rebind.
        """
        self._ntEntries.clear()
        self._ntDataTable = None

    def _getDataTable(self) -> Optional[NetworkTable]:
        """Get the data subtable from the NetworkTable."""
        if not self.ntTable:
            return None
        if self._ntDataTable is None:
            self._ntDataTable = self.ntTable.getSubTable(DataTableKey)
        return self._ntDataTable

    def _getCachedEntry(self, key: str) -> Optional[NetworkTableEntry]:
        """Get a cached NT entry or create a new one."""
        entry = self._ntEntries.get(key)
        if entry:
            return entry
        table = self._getDataTable()
        if not table:
            return None
        entry = table.getEntry(key)
        self._ntEntries[key] = entry
        return entry

    def setDataValue(self, key: str, value: Any, isMsgpack: bool = False) -> None:
        """
        Set a value in NetworkTables and optionally send via WebSocket.
        Supports all NT-compatible types.
        """
        if isinstance(value, (bytes, int, float, str, bool)):
            parsed: Any = value
        elif isinstance(value, (list, tuple)) and all(
            isinstance(x, (int, float, bytes, bool)) for x in value
        ):
            parsed = tuple(value)
        else:
            parsed = parsePipelineResult(value)

        entry = self._getCachedEntry(key)
        if entry:
            entry.setValue(parsed)

        if WebSocketServer.kInstance:
            WebSocketServer.kInstance.sendToAllSync(
                createMessage(
                    MessageTypeProto.SET_PIPELINE_RESULT,
                    PipelineResultProto(
                        is_msgpack=isMsgpack,
                        key=key,
                        value=settingValueToProto(parsed),
                        pipeline_index=self.pipelineIndex,
                    ),
                )
            )

    def setResults(self, value: TResultType | None) -> None:
        """Set the pipeline result in NT."""
        self.setDataValue(
            ResultsTopicKey,
            serializePipelineResult(value) if value is not None else 0,
            isMsgpack=True,
        )

    @overload
    def getSetting(self, setting: str) -> Optional[Any]: ...
    @overload
    def getSetting(
        self, setting: Setting[TConstraintType, TSettingValueType]
    ) -> TSettingValueType: ...

    def getSetting(self, setting: Union[Setting, str]) -> Optional[Any]:
        """Get a pipeline setting value."""
        return self.settings.getSetting(setting)

    def setSetting(self, setting: Union[Setting, str], value: SettingsValue) -> None:
        """Set a pipeline setting value."""
        settingObj = (
            setting
            if isinstance(setting, Setting)
            else self.settings.getAPI().getSetting(setting)
        )
        if settingObj:
            self.settings.setSetting(settingObj, value)
            self.onSettingChanged(settingObj, self.getSetting(setting))
        elif setting in CameraSettings():
            collection = self.getCurrentCameraSettingCollection()
            assert collection is not None
            collection.setSetting(setting, value)
        else:
            err(f"Setting {setting} was not found for pipeline {self.pipelineIndex}")

    def toDict(self, type_: str, cameraIndex: int) -> dict:
        """Return pipeline configuration as a dictionary."""
        settingsDict = self.settings.toDict()
        settingsDict.update(
            self.cameraSettings.get(cameraIndex, CameraSettings()).toDict()
        )
        return {
            "name": self.name,
            "type": type_,
            "settings": settingsDict,
        }

    def getCameraMatrix(self, cameraIndex: CameraID) -> Optional[List[List[float]]]:
        """Get 3x3 camera intrinsic matrix for the given camera."""
        camConfig = GlobalSettings.getCameraConfig(cameraIndex)
        if not camConfig:
            err("No camera matrix found, invalid results for AprilTag detection")
            return None
        currRes = self.getCameraSetting(CameraSettings.resolution)
        if currRes:
            matrixData = camConfig.calibration.get(currRes)
            if matrixData:
                lst = matrixData.matrix
                return [lst[i : i + 3] for i in range(0, 9, 3)]
        return None

    def getDistCoeffs(self, cameraIndex: CameraID) -> Optional[List[float]]:
        """Get distortion coefficients for the given camera."""
        data = GlobalSettings.getCameraConfig(cameraIndex)
        currRes = self.getCameraSetting(CameraSettings.resolution)
        if not currRes:
            return None
        if data and currRes in data.calibration:
            return data.calibration[currRes].distCoeff
        return None

    @overload
    def getCameraSetting(self, setting: str) -> Optional[Any]: ...
    @overload
    def getCameraSetting(
        self, setting: Setting[TConstraintType, TSettingValueType]
    ) -> TSettingValueType: ...

    def getCameraSetting(self, setting: Union[str, Setting]) -> Optional[Any]:
        """Get a camera-specific setting value."""
        if self.cameraIndex in self.cameraSettings:
            return self.cameraSettings[self.cameraIndex].getSetting(setting)
        return None

    def setCameraSetting(
        self, setting: Union[str, Setting], value: SettingsValue
    ) -> None:
        """Set a camera-specific setting value."""
        collection = self.getCurrentCameraSettingCollection()
        assert collection is not None
        collection.setSetting(setting, value)

    def getCurrentCameraSettingCollection(self) -> Optional[CameraSettings]:
        """Return CameraSettings for the currently bound camera."""
        return self.cameraSettings.get(self.cameraIndex)

    def onSettingChanged(self, setting: Setting, value: SettingsValue) -> None:
        """Hook called when a setting changes. Override in subclass."""
        pass


def disabled(cls):
    """Decorator to mark a pipeline as disabled."""
    cls.__is_enabled__ = False
    return cls


def pipelineToProto(inst: Pipeline, index: int, cameraId: CameraID) -> PipelineProto:
    """Serialize a pipeline instance to a PipelineProto message."""
    api: SettingsAPI = inst.settings.getAPI()
    settingsValues = {
        key: settingValueToProto(api.getValue(key))
        for key in api.getSettingsSchema().keys()
    }
    cameraSettings = inst.getCurrentCameraSettingCollection()
    if cameraSettings:
        cameraAPI = cameraSettings.getAPI()
        settingsValues.update(
            {
                key: settingValueToProto(cameraAPI.getValue(key))
                for key in cameraAPI.getSettingsSchema().keys()
            }
        )
    return PipelineProto(
        name=inst.name,
        index=index,
        type=type(inst).__name__,
        settings_values=settingsValues,
        cameraid=cameraId,
    )


TClass = TypeVar("TClass")


def pipelineName(name: str) -> Callable[[Type[TClass]], Type[TClass]]:
    """Decorator to set a pipeline type name."""

    def wrap(cls: Type[TClass]) -> Type[TClass]:
        setattr(cls, "__typename", name)
        return cls

    return wrap


def systemPipeline(
    name: Optional[str] = None,
) -> Callable[[Type[TClass]], Type[TClass]]:
    """Decorator to mark a system pipeline with a special type name."""

    def wrap(cls: Type[TClass]) -> Type[TClass]:
        resultingName: str = name or cls.__name__
        resultingName = f"$${resultingName}$$"
        setattr(cls, "__typename", resultingName)
        return cls

    return wrap


def pipelineResult(cls):
    """Decorator to create a dataclass pipeline result."""
    new_cls = type(cls.__name__, (PipelineResult, cls), dict(cls.__dict__))
    return dataclass(new_cls)


def pipelineSettings(cls):
    """Decorator to create a pipeline settings class."""
    new_cls = type(cls.__name__, (PipelineSettings, cls), dict(cls.__dict__))
    return new_cls


@lru_cache(maxsize=128)
def getPipelineTypename(pipelineType: Type[Pipeline]) -> str:
    """Return the typename for a pipeline class, cached for performance."""
    if hasattr(pipelineType, "__typename"):
        return getattr(pipelineType, "__typename")
    elif hasattr(pipelineType, "__name__"):
        return pipelineType.__name__
    else:
        return str(pipelineType)
