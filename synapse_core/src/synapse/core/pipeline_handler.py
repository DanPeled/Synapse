# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import importlib.util
import traceback
from pathlib import Path
from typing import Dict, Final, Optional, Type

import synapse.log as log

from ..callback import Callback
from ..stypes import CameraID, PipelineID, PipelineName, PipelineTypeName
from ..util import resolveGenericArgument
from .config import Config
from .global_settings import GlobalSettings
from .nt_keys import NTKeys
from .pipeline import Pipeline, getPipelineTypename
from .settings_api import CameraSettings, PipelineSettings, SettingsMap


class PipelineHandler:
    """Loads, manages, and binds pipeline configurations and instances."""

    kPipelineTypeKey: Final[str] = "type"
    kPipelineNameKey: Final[str] = "name"
    kPipelinesArrayKey: Final[str] = "pipelines"
    kPipelineFilesQuery: Final[str] = "**/*_pipeline.py"
    kInvalidPipelineIndex: Final[int] = -1

    def __init__(self, pipelineDirectory: Path):
        """Initializes the PipelineHandler with the specified directory.

        Args:
            pipelineDirectory (Path): Path to the directory containing pipeline files.
        """
        self.pipelineTypeNames: Dict[PipelineID, PipelineTypeName] = {}
        self.pipelineSettings: Dict[PipelineID, PipelineSettings] = {}
        self.pipelineInstanceBindings: Dict[PipelineID, Pipeline] = {}
        self.pipelineNames: Dict[PipelineID, PipelineName] = {}
        self.cameraPipelineSettings: Dict[
            CameraID, Dict[PipelineID, CameraSettings]
        ] = {}

        self.pipelineTypes: Dict[str, Type[Pipeline]] = {}
        self.defaultPipelineIndexes: Dict[CameraID, PipelineID] = {}

        self.pipelineDirectory: Path = pipelineDirectory

        self.onAddPipeline: Callback[PipelineID, Pipeline] = Callback()
        self.onRemovePipeline: Callback[PipelineID, Pipeline] = Callback()
        self.onDefaultPipelineSet: Callback[PipelineID, CameraID] = Callback()

    def setup(self, directory: Path):
        """Initializes the pipeline system by loading pipeline classes and their settings.

        Args:
            directory (Path): The directory containing pipeline implementations.
        """
        self.pipelineDirectory = directory
        self.pipelineTypes = self.loadPipelineTypes(directory)
        self.loadPipelineSettings()
        self.loadPipelineInstances()

    def loadPipelineInstances(self):
        for pipelineIndex in self.pipelineSettings.keys():
            pipelineType = self.getPipelineTypeByIndex(pipelineIndex)
            settings = self.pipelineSettings.get(pipelineIndex)
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
                self.pipelineNames[pipelineIndex],
                getPipelineTypename(pipelineType),
                settingsMap,
            )

    def setDefaultPipeline(
        self, cameraIndex: CameraID, pipelineIndex: PipelineID
    ) -> None:
        if pipelineIndex in self.pipelineSettings.keys():
            self.defaultPipelineIndexes[cameraIndex] = pipelineIndex
            log.log(
                f"Default Pipeline set (#{pipelineIndex}) for Camera #{cameraIndex}"
            )
            self.onDefaultPipelineSet.call(pipelineIndex, cameraIndex)
        else:
            log.err(
                f"Default Pipeline attempted to be set (#{pipelineIndex}) for Camera #{cameraIndex} but that pipeline does not exist"
            )

    def removePipeline(self, index: PipelineID) -> Optional[Pipeline]:
        if index in self.pipelineInstanceBindings:
            pipeline = self.pipelineInstanceBindings.pop(index)
            self.pipelineTypeNames.pop(index)
            self.pipelineNames.pop(index)
            self.pipelineSettings.pop(index)

            log.warn(f"Pipeline at index {index} was removed.")

            self.onRemovePipeline.call(index, pipeline)

            return pipeline
        else:
            log.warn(
                f"Attempted to remove pipeline at index {index}, but it was not found."
            )
            return None

    def addPipeline(
        self,
        index: PipelineID,
        name: str,
        typename: str,
        settings: Optional[SettingsMap] = None,
    ):
        pipelineType: Optional[Type[Pipeline]] = self.pipelineTypes.get(typename, None)
        if pipelineType is not None:
            settingsType = resolveGenericArgument(pipelineType) or PipelineSettings
            settingsInst = settingsType(settings)
            currPipeline = pipelineType(settings=settingsInst)
            currPipeline.name = name
            currPipeline.pipelineIndex = index

            self.pipelineInstanceBindings[index] = currPipeline
            self.pipelineNames[index] = name
            self.pipelineTypeNames[index] = typename
            self.pipelineSettings[index] = settingsInst

            log.log(f"Added Pipeline #{index} with type {typename}")
            self.onAddPipeline.call(index, currPipeline)

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

        pipelines = loadPipelineClasses(directory)
        pipelines.update(loadPipelineClasses(Path(__file__).parent.parent))

        log.log("Loaded pipeline classes successfully")
        return pipelines

    def loadPipelineSettings(self) -> None:
        """Loads the pipeline settings from the global configuration.

        Populates default pipelines per camera and creates settings for each pipeline.
        """
        settings: dict = Config.getInstance().getConfigMap()
        camera_configs = GlobalSettings.getCameraConfigMap()

        for cameraIndex in camera_configs:
            self.defaultPipelineIndexes[cameraIndex] = camera_configs[
                cameraIndex
            ].defaultPipeline

        pipelines: dict = settings[self.kPipelinesArrayKey]

        for pipeIndex, _ in enumerate(pipelines):
            pipeline = pipelines[pipeIndex]

            log.log(
                f"Loaded pipeline #{pipeIndex} from disk with type {pipeline[self.kPipelineTypeKey]}"
            )

            self.pipelineTypeNames[pipeIndex] = pipeline[self.kPipelineTypeKey]
            self.pipelineNames[pipeIndex] = pipeline[self.kPipelineNameKey]

            self.createPipelineSettings(
                self.pipelineTypes[self.pipelineTypeNames[pipeIndex]],
                pipeIndex,
                pipeline[NTKeys.kSettings.value],
            )

        log.log("Loaded pipeline settings successfully")

    def createPipelineSettings(
        self,
        pipelineType: Type[Pipeline],
        pipelineIndex: PipelineID,
        settings: SettingsMap,
    ) -> None:
        """Creates and stores the settings object for a given pipeline.

        Args:
            pipelineType (Type[Pipeline]): The class type of the pipeline.
            pipelineIndex (PipelineID): The index associated with this pipeline.
            settings (PipelineSettingsMap): The settings dictionary for the pipeline.
        """
        settingsType = resolveGenericArgument(pipelineType) or PipelineSettings
        self.pipelineSettings[pipelineIndex] = settingsType(settings)

    def getDefaultPipeline(self, cameraIndex: CameraID) -> PipelineID:
        """Returns the default pipeline index for a given camera.

        Args:
            cameraIndex (CameraID): The camera ID.

        Returns:
            PipelineID: The default pipeline index for the camera.
        """
        return self.defaultPipelineIndexes.get(cameraIndex, 0)

    def getPipelineSettings(self, pipelineIndex: PipelineID) -> PipelineSettings:
        """Returns the settings for a given pipeline.

        Args:
            pipelineIndex (PipelineID): The index of the pipeline.

        Returns:
            PipelineSettings: The settings object for the pipeline.
        """
        return self.pipelineSettings[pipelineIndex]

    def getPipeline(self, pipelineIndex: PipelineID) -> Optional[Pipeline]:
        """Returns the pipeline instance bound to a given index, if any.

        Args:
            pipelineIndex (PipelineID): The pipeline index.

        Returns:
            Optional[Pipeline]: The pipeline instance, or None if not bound.
        """
        if pipelineIndex in self.pipelineInstanceBindings:
            return self.pipelineInstanceBindings[pipelineIndex]
        return None

    def setPipelineInstance(
        self, pipelineIndex: PipelineID, pipeline: Pipeline
    ) -> None:
        """Binds a pipeline instance to a given index.

        Args:
            pipelineIndex (PipelineID): The pipeline index.
            pipeline (Pipeline): The pipeline instance to bind.
        """
        self.pipelineInstanceBindings[pipelineIndex] = pipeline

    def getPipelineTypeByName(self, name: PipelineName) -> Type[Pipeline]:
        """Returns the pipeline class type given its name.

        Args:
            name (PipelineName): The name of the pipeline.

        Returns:
            Type[Pipeline]: The class type of the pipeline.
        """
        return self.pipelineTypes[name]

    def getPipelineTypeByIndex(self, index: PipelineID) -> Type[Pipeline]:
        """Returns the pipeline class type given its index.

        Args:
            index (PipelineID): The pipeline index.

        Returns:
            Type[Pipeline]: The class type of the pipeline.
        """
        return self.getPipelineTypeByName(self.pipelineTypeNames[index])
