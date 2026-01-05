# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import importlib.util
import traceback
from pathlib import Path
from typing import Dict, Final, Optional, Type, TypeVar

import synapse.log as log
import yaml

from ..callback import Callback
from ..stypes import CameraID, PipelineID, PipelineName, PipelineTypeName
from ..util import resolveGenericArgument
from .camera_factory import SynapseCamera
from .config import Config
from .global_settings import GlobalSettings
from .nt_keys import NTKeys
from .pipeline import Pipeline, getPipelineTypename
from .settings_api import CameraSettings, PipelineSettings, SettingsMap

T = TypeVar("T")
CameraPipelineDict = Dict[CameraID, Dict[PipelineID, T]]


class PipelineHandler:
    """Loads, manages, and binds pipeline configurations and instances."""

    kPipelineTypeKey: Final[str] = "type"
    kPipelineNameKey: Final[str] = "name"
    kPipelinesArrayKey: Final[str] = "pipelines"
    kCameraConfigKey: Final[str] = "camera_configs"
    kPipelineFilesQuery: Final[str] = "**/*_pipeline.py"
    kInvalidPipelineIndex: Final[int] = -1

    def __init__(self, pipelineDirectory: Path):
        """Initializes the PipelineHandler with the specified directory."""

        self.pipelineTypeNames: CameraPipelineDict[PipelineTypeName] = {}
        self.pipelineSettings: CameraPipelineDict[PipelineSettings] = {}
        self.cameraPipelineSettings: CameraPipelineDict[CameraSettings] = {}
        self.pipelineInstanceBindings: CameraPipelineDict[Pipeline] = {}
        self.pipelineNames: CameraPipelineDict[PipelineName] = {}

        self.pipelineTypesViaName: Dict[str, Type[Pipeline]] = {}
        self.defaultPipelineIndexes: Dict[CameraID, PipelineID] = {}

        # Cached for latency optimization
        self._cachedPipelineTypename: Dict[Type[Pipeline], str] = {}
        self._cachedSettingsType: Dict[Type[Pipeline], Type[PipelineSettings]] = {}

        self.pipelineDirectory: Path = pipelineDirectory

        self.onAddPipeline: Callback[PipelineID, Pipeline, CameraID] = Callback()
        self.onRemovePipeline: Callback[PipelineID, Pipeline, CameraID] = Callback()
        self.onDefaultPipelineSet: Callback[PipelineID, CameraID] = Callback()

    def setup(self, directory: Path):
        """Initializes the pipeline system by loading pipeline classes and their settings."""
        self.pipelineDirectory = directory
        self.pipelineTypesViaName = self.loadPipelineTypes(directory)
        self.loadPipelineSettings()
        self.loadPipelineCameraSettings()
        self.loadPipelineInstances()

    def onAddCamera(
        self, cameraIndex: CameraID, name: str, camera: SynapseCamera
    ) -> None:
        if cameraIndex not in self.pipelineInstanceBindings.keys():
            self.pipelineInstanceBindings[cameraIndex] = {}
        if cameraIndex not in self.pipelineNames:
            self.pipelineNames[cameraIndex] = {}
        if cameraIndex not in self.pipelineSettings:
            self.pipelineSettings[cameraIndex] = {}
        if cameraIndex not in self.pipelineTypeNames:
            self.pipelineTypeNames[cameraIndex] = {}
        if cameraIndex not in self.defaultPipelineIndexes:
            self.defaultPipelineIndexes[cameraIndex] = 0
        if cameraIndex not in self.cameraPipelineSettings:
            self.cameraPipelineSettings[cameraIndex] = {}

    def loadPipelineCameraSettings(self):
        camera_configs = GlobalSettings.getCameraConfigMap()
        for cameraid in camera_configs.keys():
            path = (
                Config.getInstance().path.parent
                / f"camera_{cameraid}"
                / "pipeline_settings.yml"
            )
            if not path.exists():
                continue

            with open(path, "r") as f:
                config = yaml.full_load(f) or {}

            if cameraid not in self.cameraPipelineSettings:
                self.cameraPipelineSettings[cameraid] = {}

            for pipelineid, pipedata in (config.get("pipeline_configs") or {}).items():
                self.cameraPipelineSettings[cameraid][pipelineid] = CameraSettings(
                    pipedata["settings"]
                )

    def loadPipelineInstances(self):
        for cameraid in self.pipelineSettings.keys():
            for pipelineIndex in self.pipelineSettings[cameraid].keys():
                pipelineType = self.getPipelineTypeByIndex(pipelineIndex, cameraid)
                settings = self.pipelineSettings[cameraid].get(pipelineIndex)
                settingsMap: Dict = {}
                if settings:
                    settingsMap = {
                        key: settings.getAPI().getValue(key)
                        for key in settings.getSchema().keys()
                    }
                else:
                    settingsMap = {}

                self.addPipeline(
                    pipelineIndex,
                    self.pipelineNames[cameraid][pipelineIndex],
                    getPipelineTypename(pipelineType),
                    cameraid,
                    settingsMap,
                )

    def setDefaultPipeline(
        self, cameraIndex: CameraID, pipelineIndex: PipelineID
    ) -> None:
        if pipelineIndex in self.pipelineSettings[cameraIndex].keys():
            self.defaultPipelineIndexes[cameraIndex] = pipelineIndex
            log.log(
                f"Default Pipeline set (#{pipelineIndex}) for Camera #{cameraIndex}"
            )
            self.onDefaultPipelineSet.call(pipelineIndex, cameraIndex)
        else:
            log.err(
                f"Default Pipeline attempted to be set (#{pipelineIndex}) for Camera #{cameraIndex} but that pipeline does not exist"
            )

    def removePipeline(
        self, index: PipelineID, cameraid: CameraID
    ) -> Optional[Pipeline]:
        # check inside the camera's pipeline instances
        if (
            cameraid in self.pipelineInstanceBindings
            and index in self.pipelineInstanceBindings[cameraid]
        ):
            pipeline = self.pipelineInstanceBindings[cameraid].pop(index, None)
            if pipeline is not None:
                # remove metadata for that pipeline *for that camera*
                if cameraid in self.pipelineTypeNames:
                    self.pipelineTypeNames[cameraid].pop(index, None)
                if cameraid in self.pipelineNames:
                    self.pipelineNames[cameraid].pop(index, None)
                if cameraid in self.pipelineSettings:
                    self.pipelineSettings[cameraid].pop(index, None)

                log.warn(
                    f"Pipeline at index {index} was removed from camera {cameraid}."
                )

                self.onRemovePipeline.call(index, pipeline, cameraid)

                return pipeline

        log.warn(
            f"Attempted to remove pipeline at index {index} for camera {cameraid}, but it was not found."
        )
        return None

    def addPipeline(
        self,
        index: PipelineID,
        name: str,
        typename: str,
        cameraid: CameraID,
        settings: Optional[SettingsMap] = None,
    ):
        pipelineType: Optional[Type[Pipeline]] = self.pipelineTypesViaName.get(
            typename, None
        )
        if pipelineType is not None:
            # Use cached settings type
            if pipelineType not in self._cachedSettingsType:
                self._cachedSettingsType[pipelineType] = (
                    resolveGenericArgument(pipelineType) or PipelineSettings
                )
            settingsType = self._cachedSettingsType[pipelineType]

            settingsInst = settingsType(settings)
            currPipeline = pipelineType(settings=settingsInst)

            # Use cached typename
            if pipelineType not in self._cachedPipelineTypename:
                self._cachedPipelineTypename[pipelineType] = getPipelineTypename(
                    pipelineType
                )
            currPipeline.name = name
            currPipeline.pipelineIndex = index
            currPipeline.cameraIndex = cameraid

            if cameraid not in self.cameraPipelineSettings:
                self.cameraPipelineSettings[cameraid] = {index: CameraSettings()}
            elif index not in self.cameraPipelineSettings[cameraid]:
                self.cameraPipelineSettings[cameraid][index] = CameraSettings()

            assert (
                cameraid in self.cameraPipelineSettings
                and index in self.cameraPipelineSettings[cameraid]
            )

            currPipeline.cameraSettings = self.cameraPipelineSettings[cameraid][index]

            # Ensure camera dictionaries exist
            self.pipelineInstanceBindings.setdefault(cameraid, {})
            self.pipelineNames.setdefault(cameraid, {})
            self.pipelineSettings.setdefault(cameraid, {})
            self.pipelineTypeNames.setdefault(cameraid, {})

            self.pipelineInstanceBindings[cameraid][index] = currPipeline
            self.pipelineNames[cameraid][index] = name
            self.pipelineTypeNames[cameraid][index] = typename
            self.pipelineSettings[cameraid][index] = settingsInst

            log.log(
                f"Added Pipeline #{index} with type {typename} to camera #{cameraid}"
            )
            self.onAddPipeline.call(index, currPipeline, cameraid)

    def loadPipelineTypes(self, directory: Path) -> Dict[PipelineName, Type[Pipeline]]:
        """Loads all classes that extend Pipeline from Python files in the directory.

        Args:
            directory (Path): The root directory to search for pipeline implementations.

        Returns:
            Dict[PipelineName, Type[Pipeline]]: A dictionary mapping pipeline names to their types.
        """
        ignoredFiles: Final[list] = ["setup.py"]

        def loadPipelineClasses(directory: Path):
            """Helper function to load pipeline classes from files in a directory.

            Args:
                directory (Path): The directory to search.

            Returns:
                Dict[str, Type[Pipeline]]: Loaded pipeline classes found in the directory.
            """
            pipelineClasses = {}
            for file_path in directory.rglob(PipelineHandler.kPipelineFilesQuery):
                if file_path.name not in ignoredFiles:
                    module_name = file_path.stem

                    try:
                        spec = importlib.util.spec_from_file_location(
                            module_name, str(file_path)
                        )
                        if spec is None or spec.loader is None:
                            continue

                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)

                        for attr in dir(module):
                            cls = getattr(module, attr)
                            if (
                                isinstance(cls, type)
                                and issubclass(cls, Pipeline)
                                and cls is not Pipeline
                            ):
                                if cls.__is_enabled__:
                                    log.log(
                                        f"Loaded {getPipelineTypename(cls)} pipeline"
                                    )
                                    pipelineClasses[getPipelineTypename(cls)] = cls
                    except Exception as e:
                        log.err(
                            f"while loading {file_path}: {e}\n{traceback.format_exc()}"
                        )
            return pipelineClasses

        def is_inside(child, parent):
            child = Path(child).resolve()
            parent = Path(parent).resolve()
            return parent in child.parents

        pipelines = loadPipelineClasses(directory)
        if not is_inside(Path(__file__), directory):
            # When running on coprocessor, this file's root dir
            # is as the same as the main.py file which will result
            # in reading this file twice when reading from the project dir and this dir
            pipelines.update(loadPipelineClasses(Path(__file__).parent.parent))

        log.log("Loaded pipeline classes successfully")
        return pipelines

    def loadPipelineSettings(self) -> None:
        """Loads the pipeline settings from the global configuration.

        Populates default pipelines per camera and creates settings for each pipeline.
        """
        camera_configs = GlobalSettings.getCameraConfigMap()

        for cameraIndex in camera_configs:
            self.defaultPipelineIndexes[cameraIndex] = camera_configs[
                cameraIndex
            ].defaultPipeline

        for cameraIndex in camera_configs.keys():
            with open(
                Config.getInstance().path.parent
                / f"camera_{cameraIndex}"
                / "pipeline_settings.yml"
            ) as f:
                pipeline_configs = yaml.full_load(f)
                for pipelineIndex, pipeline in pipeline_configs[
                    "pipeline_configs"
                ].items():
                    log.log(
                        f"Loaded pipeline #{pipelineIndex} (Camera #{cameraIndex}) from disk with type {pipeline[self.kPipelineTypeKey]}"
                    )

                    if cameraIndex not in self.pipelineTypeNames:
                        self.pipelineTypeNames[cameraIndex] = {}
                        self.pipelineNames[cameraIndex] = {}

                    self.pipelineTypeNames[cameraIndex][pipelineIndex] = pipeline[
                        self.kPipelineTypeKey
                    ]
                    self.pipelineNames[cameraIndex][pipelineIndex] = pipeline[
                        self.kPipelineNameKey
                    ]

                    self.createPipelineSettings(
                        self.pipelineTypesViaName[
                            self.pipelineTypeNames[cameraIndex][pipelineIndex]
                        ],
                        pipelineIndex,
                        pipeline[NTKeys.kSettings.value],
                        cameraid=cameraIndex,
                    )

        log.log("Loaded pipeline settings successfully")

    def createPipelineSettings(
        self,
        pipelineType: Type[Pipeline],
        pipelineIndex: PipelineID,
        settings: SettingsMap,
        cameraid: CameraID,
    ) -> None:
        """Creates and stores the settings object for a given pipeline.

        Args:
            pipelineType (Type[Pipeline]): The class type of the pipeline.
            pipelineIndex (PipelineID): The index associated with this pipeline.
            settings (PipelineSettingsMap): The settings dictionary for the pipeline.
        """
        settingsType = resolveGenericArgument(pipelineType) or PipelineSettings
        if cameraid not in self.pipelineSettings:
            self.pipelineSettings[cameraid] = {}
        self.pipelineSettings[cameraid][pipelineIndex] = settingsType(settings)

    def getDefaultPipeline(self, cameraIndex: CameraID) -> PipelineID:
        """Returns the default pipeline index for a given camera.

        Args:
            cameraIndex (CameraID): The camera ID.

        Returns:
            PipelineID: The default pipeline index for the camera.
        """
        return self.defaultPipelineIndexes.get(cameraIndex, 0)

    def getPipelineSettings(
        self, pipelineIndex: PipelineID, cameraid: CameraID
    ) -> PipelineSettings:
        """Returns the settings for a given pipeline.

        Args:
            pipelineIndex (PipelineID): The index of the pipeline.

        Returns:
            PipelineSettings: The settings object for the pipeline.
        """
        return self.pipelineSettings[cameraid][pipelineIndex]

    def getPipeline(
        self, pipelineIndex: PipelineID, cameraid: CameraID
    ) -> Optional[Pipeline]:
        """Returns the pipeline instance bound to a given index, if any.

        Args:
            pipelineIndex (PipelineID): The pipeline index.

        Returns:
            Optional[Pipeline]: The pipeline instance, or None if not bound.
        """
        if cameraid in self.pipelineInstanceBindings:
            return self.pipelineInstanceBindings[cameraid].get(pipelineIndex)
        return None

    def setPipelineInstance(
        self, pipelineIndex: PipelineID, pipeline: Pipeline, cameraid: CameraID
    ) -> None:
        """Binds a pipeline instance to a given index.

        Args:
            pipelineIndex (PipelineID): The pipeline index.
            pipeline (Pipeline): The pipeline instance to bind.
        """
        self.pipelineInstanceBindings[cameraid][pipelineIndex] = pipeline

    def getPipelineTypeByName(self, name: PipelineName) -> Type[Pipeline]:
        """Returns the pipeline class type given its name.

        Args:
            name (PipelineName): The name of the pipeline.

        Returns:
            Type[Pipeline]: The class type of the pipeline.
        """
        return self.pipelineTypesViaName[name]

    def getPipelineTypeByIndex(
        self, index: PipelineID, cameraID: CameraID
    ) -> Type[Pipeline]:
        """Returns the pipeline class type given its index.

        Args:
            index (PipelineID): The pipeline index.

        Returns:
            Type[Pipeline]: The class type of the pipeline.
        """
        return self.getPipelineTypeByName(self.pipelineTypeNames[cameraID][index])
