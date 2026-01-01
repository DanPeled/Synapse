# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
import os
import threading
import time
import traceback
from pathlib import Path
from typing import Any, List, Optional

import psutil
from synapse_installer.util import IsValidIP
from synapse_net.devicenetworking import NetworkingManager
from synapse_net.file_server import FileServer
from synapse_net.nt_client import NtClient, RemoteConnectionIP
from synapse_net.proto.v1 import (DeviceInfoProto, MessageProto,
                                  MessageTypeProto, PipelineProto,
                                  PipelineTypeProto,
                                  RemovePipelineMessageProto,
                                  SetCameraRecordingStatusMessageProto,
                                  SetConnectionInfoProto,
                                  SetDefaultPipelineMessageProto,
                                  SetNetworkSettingsProto,
                                  SetPipelineIndexMessageProto,
                                  SetPipelineNameMessageProto,
                                  SetPipleineSettingMessageProto)
from synapse_net.socketServer import (SocketEvent, WebSocketServer, assert_set,
                                      createMessage)
from synapse_net.ui_handle import UIHandle

from synapse_net import devicenetworking

from ..bcolors import MarkupColors
from ..hardware.deviceactions import reboot
from ..hardware.metrics import Platform
from ..log import err, log, logs, missingFeature, warn
from ..stypes import (CameraID, CameraName, PipelineID, RecordingFilename,
                      RecordingStatus)
from ..util import getIP, resolveGenericArgument
from .camera_factory import SynapseCamera
from .config import Config, NetworkConfig
from .global_settings import GlobalSettings
from .pipeline import Pipeline, pipelineToProto
from .runtime_handler import RuntimeManager
from .settings_api import (cameraToProto, protoToSettingValue, settingsToProto,
                           settingValueToProto)


class Synapse:
    """
    handles the initialization and running of the Synapse runtime, including network setup and loading global settings.

        Attributes:
            runtime_handler (RuntimeManager): The handler responsible for managing the pipelines' lifecycles.
            settings_dict (dict): A dictionary containing the configuration settings loaded from the `settings.yml` file.
            nt_client (NtClient): The instance of NtClient used to manage the NetworkTables connection.
    """

    kInstance: "Synapse"

    def __init__(self) -> None:
        self.runtimeHandler: RuntimeManager
        self.networkingManager = NetworkingManager()
        self.ntClient: NtClient = NtClient()
        self.fileServer: Optional[FileServer] = None

    def init(
        self,
        runtimeHandler: RuntimeManager,
        configPath: Path,
    ) -> bool:
        """
        Initializes the Synapse pipeline by loading configuration settings and setting up NetworkTables and global settings.

        Args:
            runtime_handler (RuntimeManager): The handler responsible for managing the pipeline's lifecycle.
            config_path (str, optional): The path to the configuration file. Defaults to "./config/settings.yml".

        Returns:
            bool: True if initialization was successful, False otherwise.
        """
        Synapse.kInstance = self

        platform = Platform.getCurrentPlatform()

        if platform.isWindows():
            os.system("cls")
        else:
            os.system("clear")

        UIHandle.startUI()

        log(
            MarkupColors.bold(
                MarkupColors.okgreen(
                    "\n" + "=" * 20 + " Synapse Initialize Starting... " + "=" * 20
                )
            )
        )

        self.runtimeHandler = runtimeHandler
        self.setupRuntimeCallbacks()

        self.setupWebsocket()

        self.fileServer = FileServer(configPath.parent.parent)
        self.fileServer.start()

        if configPath.exists():
            ...
        else:
            log("No config file!")
            configPath.parent.mkdir(exist_ok=True)
            with open(configPath, "w") as _:
                ...
        try:
            config = Config()
            config.load(filePath=configPath)
            self.runtimeHandler.networkSettings = config.network

            if (
                config.network.ip is not None
                and config.network.networkInterface is not None
            ):
                self.networkingManager.configureStaticIp(
                    config.network.ip, config.network.networkInterface
                )

            # Load the settings from the config file
            settings: dict = config.getConfigMap()
            self.settings_dict = settings

            global_settings = {}
            if "global" in settings:
                global_settings = settings["global"]
            if not GlobalSettings.setup(global_settings):
                raise Exception("Global settings setup failed")

            # Initialize NetworkTables
            self.__init_cmd_args()

            log(
                f"Network Config:\n  Team Number: {config.network.teamNumber}\n  Name: {config.network.name}\n  Is Server: {self.__isServer}\n  Is Sim: {self.__isSim}"
            )

            nt_good = self.__init_networktables(config.network)
            if nt_good:
                self.runtimeHandler.setup(Path(os.getcwd()))
            else:
                err(
                    f"Something went wrong while setting up networktables with params: {config.network}"
                )
                return False

            # Setup global settings
        except Exception as error:
            errString = "".join(
                traceback.format_exception(type(error), error, error.__traceback__)
            )
            log(f"Something went wrong while reading settings config file. {errString}")
            raise error
        return True

    def __init_networktables(self, settings: NetworkConfig) -> bool:
        """
        Initializes the NetworkTables client with the provided settings.

        Args:
            settings (dict): A dictionary containing the NetworkTables settings such as `server_ip`, `name`, and `server` status.

        Returns:
            bool: True if NetworkTables was successfully initialized, False otherwise.
        """
        setup_good = self.ntClient.setup(
            teamNumber=settings.teamNumber,
            name=settings.name,
            isServer=self.__isServer,
            isSim=self.__isSim,
        )

        return setup_good

    def __init_cmd_args(self) -> None:
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--server", action="store_true", help="Run in server mode")
        parser.add_argument("--sim", action="store_true", help="Run in sim mode")
        args = parser.parse_args()

        if args.server:
            self.__isServer = True
        else:
            self.__isServer = False
        if args.sim:
            self.__isSim = True
        else:
            self.__isSim = False

    def run(self) -> None:
        """
        Starts the pipeline by loading the settings and executing the pipeline handler.

        This method is responsible for running the pipeline after it has been initialized.
        """
        self.runtimeHandler.run()

    def setupWebsocket(self) -> None:
        import asyncio

        import psutil

        self.websocket = WebSocketServer("0.0.0.0", 8765)

        # Create a new asyncio event loop for the websocket thread
        new_loop = asyncio.new_event_loop()
        self.websocket.loop = new_loop  # store for shutdown

        @self.websocket.on(SocketEvent.kConnect)
        async def on_connect(ws):
            import synapse.hardware.metrics as metrics

            from ..__version__ import SYNAPSE_VERSION

            if self.ntClient:
                connectionDetails = SetConnectionInfoProto(
                    connected_to_networktables=self.ntClient.nt_inst.isConnected()
                )

                await self.websocket.sendToClient(
                    ws,
                    createMessage(
                        MessageTypeProto.SET_DEVICE_CONNECTION_STATUS, connectionDetails
                    ),
                )

            deviceInfo: DeviceInfoProto = DeviceInfoProto(
                ip=getIP(),
                version=SYNAPSE_VERSION,
                platform=metrics.Platform.getCurrentPlatform().getOSType().value,
                hostname=self.runtimeHandler.networkSettings.hostname,
            )

            deviceInfo.network_interfaces.extend(psutil.net_if_addrs().keys())

            await self.websocket.sendToClient(
                ws,
                createMessage(
                    MessageTypeProto.SET_NETWORK_SETTINGS,
                    self.runtimeHandler.networkSettings.toProto(),
                ),
            )

            await self.websocket.sendToClient(
                ws,
                createMessage(
                    MessageTypeProto.SEND_DEVICE_INFO,
                    deviceInfo,
                ),
            )

            while not self.runtimeHandler.isSetup:
                try:
                    time.sleep(0.1)
                except Exception:
                    ...

            for (
                cameraid,
                pipelines,
            ) in self.runtimeHandler.pipelineHandler.pipelineInstanceBindings.items():
                for id, pipeline in pipelines.items():
                    msg = pipelineToProto(pipeline, id, cameraid)

                    await self.websocket.sendToAll(
                        createMessage(MessageTypeProto.ADD_PIPELINE, msg)
                    )

            typeMessages: List[PipelineTypeProto] = []
            for (
                typename,
                type,
            ) in self.runtimeHandler.pipelineHandler.pipelineTypesViaName.items():
                settingType = resolveGenericArgument(type)
                if settingType:
                    settings = settingType({})
                    settingsProto = settingsToProto(settings, typename)
                    typeMessages.append(
                        PipelineTypeProto(type=typename, settings=settingsProto)
                    )

            await self.websocket.sendToAll(
                MessageProto(
                    MessageTypeProto.SEND_PIPELINE_TYPES,
                    pipeline_type_info=typeMessages,
                ).SerializeToString()
            )

            for id, camera in self.runtimeHandler.cameraHandler.cameras.items():
                msg = cameraToProto(
                    id,
                    camera.name,
                    camera,
                    self.runtimeHandler.pipelineBindings.get(id, 0),
                    self.runtimeHandler.pipelineHandler.defaultPipelineIndexes.get(
                        id, -1
                    ),
                    self.runtimeHandler.cameraHandler.cameraConfigBindings[id].id,
                )

                await self.websocket.sendToAll(
                    createMessage(MessageTypeProto.ADD_CAMERA, msg)
                )

            for (
                id,
                config,
            ) in self.runtimeHandler.cameraHandler.cameraConfigBindings.items():
                calibrations = config.calibration

                for calib in calibrations.values():
                    calibProto = calib.toProto(id)
                    await self.websocket.sendToAll(
                        MessageProto(
                            type=MessageTypeProto.CALIBRATION_DATA,
                            calibration_data=calibProto,
                        ).SerializeToString()
                    )

            for log_ in logs:
                msg = createMessage(MessageTypeProto.LOG, log_)
                await self.websocket.sendToAll(msg)

        @self.websocket.on(SocketEvent.kMessage)
        async def on_message(ws, msg):
            self.onMessage(ws, msg)

        @self.websocket.on(SocketEvent.kError)
        async def on_error(ws, error_msg):
            err(f"Socket: {ws.remote_address}: {error_msg}")

        def start_loop(loop):
            asyncio.set_event_loop(loop)
            loop.run_forever()

        # Create daemon thread so it won't block process exit
        self.websocketThread = threading.Thread(
            target=start_loop, args=(new_loop,), daemon=True
        )
        self.websocketThread.start()

        async def run_server():
            await self.websocket.start()

        # Schedule the websocket server start coroutine in the new event loop
        asyncio.run_coroutine_threadsafe(run_server(), new_loop)

        log("WebSocket server started on ws://localhost:8765")

    def cleanup(self):
        if NtClient.INSTANCE is not None:
            NtClient.INSTANCE.cleanup()

        if self.websocket.loop is not None:
            future = asyncio.run_coroutine_threadsafe(
                self.websocket.close(), self.websocket.loop
            )
            try:
                future.result(timeout=5)
            except Exception as e:
                err(f"Error while closing websocket: {e}")

            self.websocket.loop.call_soon_threadsafe(self.websocket.loop.stop)

        if self.fileServer is not None:
            self.fileServer.stop()

        # Only join if not current thread
        if self.websocketThread is not threading.current_thread():
            self.websocketThread.join(timeout=5)

        self.runtimeHandler.cleanup()

    def setupRuntimeCallbacks(self):
        def onAddPipeline(id: PipelineID, inst: Pipeline, cameraid: CameraID) -> None:
            pipelineProto = pipelineToProto(inst, id, cameraid)

            Synapse.kInstance.websocket.sendToAllSync(
                createMessage(MessageTypeProto.ADD_PIPELINE, pipelineProto)
            )

        def onAddCamera(cameraid: CameraID, name: str, camera: SynapseCamera) -> None:
            cameraProto = cameraToProto(
                cameraid,
                name,
                camera,
                self.runtimeHandler.pipelineBindings.get(cameraid, 0),
                self.runtimeHandler.pipelineHandler.defaultPipelineIndexes.get(
                    cameraid, 0
                ),
                self.runtimeHandler.cameraHandler.cameraConfigBindings[cameraid].id,
            )

            Synapse.kInstance.websocket.sendToAllSync(
                createMessage(MessageTypeProto.ADD_CAMERA, cameraProto)
            )

        def onSettingChangedInNt(
            setting: str, value: Any, cameraIndex: CameraID
        ) -> None:
            setSettingProto: SetPipleineSettingMessageProto = (
                SetPipleineSettingMessageProto(
                    setting=setting,
                    value=settingValueToProto(value),
                    pipeline_index=Synapse.kInstance.runtimeHandler.pipelineBindings[
                        cameraIndex
                    ],
                    cameraid=cameraIndex,
                )
            )

            msg = createMessage(MessageTypeProto.SET_SETTING, setSettingProto)

            Synapse.kInstance.websocket.sendToAllSync(msg)

        def onPipelineIndexChangedInNt(
            pipelineIndex: PipelineID, cameraIndex: CameraID
        ) -> None:
            setPipelineIndexProto: SetPipelineIndexMessageProto = (
                SetPipelineIndexMessageProto(
                    pipeline_index=pipelineIndex, camera_index=cameraIndex
                )
            )

            msg = createMessage(
                MessageTypeProto.SET_PIPELINE_INDEX, setPipelineIndexProto
            )

            Synapse.kInstance.websocket.sendToAllSync(msg)

        def onDefaultPipelineSet(pipelineIndex: PipelineID, cameraIndex: CameraID):
            camera: Optional[SynapseCamera] = (
                Synapse.kInstance.runtimeHandler.cameraHandler.getCamera(cameraIndex)
            )
            if camera:
                cameraMsg = cameraToProto(
                    cameraIndex,
                    camera.name,
                    camera,
                    pipelineIndex=self.runtimeHandler.pipelineBindings[cameraIndex],
                    defaultPipeline=pipelineIndex,
                    kind=self.runtimeHandler.cameraHandler.cameraConfigBindings[
                        cameraIndex
                    ].id,
                )
                msg = createMessage(MessageTypeProto.ADD_CAMERA, cameraMsg)

                Synapse.kInstance.websocket.sendToAllSync(msg)

        def onCameraRename(cameraIndex: CameraID, newName: CameraName):
            camera = self.runtimeHandler.cameraHandler.cameras[cameraIndex]
            cameraMsg = cameraToProto(
                cameraIndex,
                camera.name,
                camera,
                pipelineIndex=self.runtimeHandler.pipelineBindings[cameraIndex],
                defaultPipeline=self.runtimeHandler.pipelineHandler.defaultPipelineIndexes[
                    cameraIndex
                ],
                kind=self.runtimeHandler.cameraHandler.cameraConfigBindings[
                    cameraIndex
                ].id,
            )
            msg = createMessage(MessageTypeProto.ADD_CAMERA, cameraMsg)
            self.websocket.sendToAllSync(msg)
            self.runtimeHandler.save()

        def onCameraRecordingStatusChanged(
            cameraIndex: CameraID, status: RecordingStatus, filename: RecordingFilename
        ) -> None:
            msg = createMessage(
                MessageTypeProto.SET_CAMERA_RECORDING_STATUS,
                SetCameraRecordingStatusMessageProto(
                    record=status, camera_index=cameraIndex
                ),
            )

            self.websocket.sendToAllSync(msg)

        def onConnect(ip: RemoteConnectionIP) -> None:
            connectionDetails = SetConnectionInfoProto(connected_to_networktables=True)

            self.websocket.sendToAllSync(
                createMessage(
                    MessageTypeProto.SET_DEVICE_CONNECTION_STATUS, connectionDetails
                ),
            )

        def onDisconnect(ip: RemoteConnectionIP) -> None:
            connectionDetails = SetConnectionInfoProto(connected_to_networktables=False)

            self.websocket.sendToAllSync(
                createMessage(
                    MessageTypeProto.SET_DEVICE_CONNECTION_STATUS, connectionDetails
                ),
            )

        self.runtimeHandler.pipelineHandler.onAddPipeline.add(onAddPipeline)
        self.runtimeHandler.cameraHandler.onAddCamera.add(onAddCamera)
        self.runtimeHandler.onSettingChangedFromNT.add(onSettingChangedInNt)
        self.runtimeHandler.onPipelineChanged.add(onPipelineIndexChangedInNt)
        self.runtimeHandler.pipelineHandler.onDefaultPipelineSet.add(
            onDefaultPipelineSet
        )
        self.runtimeHandler.cameraHandler.onRenameCamera.add(onCameraRename)
        self.runtimeHandler.cameraHandler.onRecordingStatusChanged.add(
            onCameraRecordingStatusChanged
        )
        self.ntClient.onConnect.add(onConnect)
        self.ntClient.onDisconnect.add(onDisconnect)

    def onMessage(self, ws, msg) -> None:
        msgObj = MessageProto().parse(msg)
        msgType = msgObj.type

        if msgType == MessageTypeProto.SET_SETTING:
            assert_set(msgObj.set_pipeline_setting)
            setSettingMSG: SetPipleineSettingMessageProto = msgObj.set_pipeline_setting

            pipeline: Optional[Pipeline] = (
                self.runtimeHandler.pipelineHandler.getPipeline(
                    setSettingMSG.pipeline_index, setSettingMSG.cameraid
                )
            )

            if pipeline is not None:
                val = protoToSettingValue(setSettingMSG.value)
                pipeline.setSetting(setSettingMSG.setting, val)
                self.runtimeHandler.updateSetting(
                    setSettingMSG.setting, setSettingMSG.cameraid, val
                )
            else:
                err(
                    f"Attempted to set setting on non-existing pipeline (id={setSettingMSG.pipeline_index}, cameraid={setSettingMSG.cameraid})"
                )
        elif msgType == MessageTypeProto.SET_PIPELINE_INDEX:
            assert_set(msgObj.set_pipeline_index)
            setPipeIndexMSG: SetPipelineIndexMessageProto = msgObj.set_pipeline_index
            self.runtimeHandler.setPipelineByIndex(
                cameraIndex=setPipeIndexMSG.camera_index,
                pipelineIndex=setPipeIndexMSG.pipeline_index,
            )
        elif msgType == MessageTypeProto.SET_PIPELINE_NAME:
            assert_set(msgObj.set_pipeline_name)
            setPipelineNameMsg: SetPipelineNameMessageProto = msgObj.set_pipeline_name
            pipeline: Optional[Pipeline] = (
                self.runtimeHandler.pipelineHandler.getPipeline(
                    setPipelineNameMsg.pipeline_index, setPipelineNameMsg.cameraid
                )
            )
            if pipeline is not None:
                pipeline.name = setPipelineNameMsg.name
                log(
                    f"Changed name for pipeline #{setPipelineNameMsg.pipeline_index} to `{setPipelineNameMsg.name}`"
                )

                response: bytes = createMessage(
                    MessageTypeProto.SET_PIPELINE_NAME,
                    SetPipelineNameMessageProto(
                        pipeline_index=setPipelineNameMsg.pipeline_index,
                        name=pipeline.name,
                    ),
                )

                Synapse.kInstance.websocket.sendToAllSync(response)
            else:
                err(
                    f'Attempted name modification ("{setPipelineNameMsg.name}") for non-existing pipeline in index: {setPipelineNameMsg.pipeline_index}'
                )
        elif msgType == MessageTypeProto.ADD_PIPELINE:
            assert_set(msgObj.pipeline_info)
            addPipelineMsg: PipelineProto = msgObj.pipeline_info
            if addPipelineMsg.type is not None and (
                addPipelineMsg.type
                in self.runtimeHandler.pipelineHandler.pipelineTypesViaName.keys()
            ):
                self.runtimeHandler.pipelineHandler.addPipeline(
                    index=addPipelineMsg.index,
                    name=addPipelineMsg.name,
                    typename=addPipelineMsg.type,
                    cameraid=addPipelineMsg.cameraid,
                    settings={
                        key: protoToSettingValue(valueProto)
                        for key, valueProto in addPipelineMsg.settings_values.items()
                    },
                )

                pipeline = self.runtimeHandler.pipelineHandler.getPipeline(
                    addPipelineMsg.index, addPipelineMsg.cameraid
                )
                if pipeline is not None:
                    camera = self.runtimeHandler.cameraHandler.getCamera(
                        addPipelineMsg.cameraid
                    )
                    assert camera is not None

                    pipeline.bind(addPipelineMsg.cameraid, camera)
            else:
                err(
                    f"Cannot add pipeline of type {addPipelineMsg.type}, it is an invalid typename"
                )
        elif msgType == MessageTypeProto.DELETE_PIPELINE:
            assert_set(msgObj.remove_pipeline)
            removePipelineMessage: RemovePipelineMessageProto = msgObj.remove_pipeline
            self.runtimeHandler.pipelineHandler.removePipeline(
                removePipelineMessage.remove_pipeline_index,
                removePipelineMessage.cameraid,
            )
        elif msgType == MessageTypeProto.SET_DEFAULT_PIPELINE:
            assert_set(msgObj.set_default_pipeline)
            defaultPipelineMsg: SetDefaultPipelineMessageProto = (
                msgObj.set_default_pipeline
            )
            self.runtimeHandler.pipelineHandler.setDefaultPipeline(
                cameraIndex=defaultPipelineMsg.camera_index,
                pipelineIndex=defaultPipelineMsg.pipeline_index,
            )
        elif msgType == MessageTypeProto.SAVE:
            self.runtimeHandler.save()
        elif msgType == MessageTypeProto.SET_NETWORK_SETTINGS:
            assert_set(msgObj.set_network_settings)
            networkSettings: SetNetworkSettingsProto = msgObj.set_network_settings
            self.setNetworkSettings(networkSettings)
        elif msgType == MessageTypeProto.REBOOT:
            reboot()
        elif msgType == MessageTypeProto.FORMAT:
            configFilePath = Config.getInstance().path
            os.remove(configFilePath)
            warn("Config file deleted! all settings will be lost")
            self.close()
            reboot()
        elif msgType == MessageTypeProto.RESTART_SYNAPSE:
            warn(
                "Attempting to restart Synapse, may cause some unexpected results\nCurrently works only for robot coprocessors"
            )
            self.close()
        elif msgType == MessageTypeProto.RENAME_CAMERA:
            assert_set(msgObj.rename_camera)
            renameCameraMsg = msgObj.rename_camera

            self.runtimeHandler.cameraHandler.renameCamera(
                renameCameraMsg.camera_index, renameCameraMsg.new_name
            )
        elif msgType == MessageTypeProto.DELETE_CALIBRATION:
            assert_set(msgObj.delete_calibration)
            deleteCalibrationMsg = msgObj.delete_calibration

            if (
                deleteCalibrationMsg.camera_index
                in self.runtimeHandler.cameraHandler.cameraConfigBindings
            ):
                self.runtimeHandler.cameraHandler.cameraConfigBindings[
                    deleteCalibrationMsg.camera_index
                ].calibration.pop(deleteCalibrationMsg.resolution)

                # TODO Send back delete message to let the client know its been deleted
        elif msgType == MessageTypeProto.SET_CAMERA_RECORDING_STATUS:
            assert_set(msgObj.set_camera_recording_status)

            setRecordingStatusMsg = msgObj.set_camera_recording_status

            self.runtimeHandler.cameraHandler.setRecordingStatus(
                setRecordingStatusMsg.camera_index, setRecordingStatusMsg.record
            )

    def setNetworkSettings(self, networkSettings: SetNetworkSettingsProto) -> None:
        if Platform.getCurrentPlatform().isLinux():
            network_interfaces = []
            network_interfaces.extend(psutil.net_if_addrs().keys())

            if (
                IsValidIP(networkSettings.ip)
                and networkSettings.network_interface in network_interfaces
            ):
                self.networkingManager.configureStaticIp(
                    networkSettings.ip, networkSettings.network_interface
                )
                self.runtimeHandler.networkSettings.ip = networkSettings.ip
                self.runtimeHandler.networkSettings.networkInterface = (
                    networkSettings.network_interface
                )
            elif (
                networkSettings.ip == "NULL"
            ):  # Don't configure static IP and remove if config exists
                self.runtimeHandler.networkSettings.ip = None
                self.networkingManager.removeStaticIp()
            else:
                err(f"Invalid IP {networkSettings.ip} provided! Will be ignored")

            if networkSettings.hostname.__len__() > 0:
                self.runtimeHandler.networkSettings.hostname = networkSettings.hostname
                devicenetworking.setHostname(networkSettings.hostname)
            else:
                err("Empty hostname isn't allowed!")
        else:
            missingFeature(
                "Non-Linux systems network and system settings modification isn't supported at the time"
            )

        self.runtimeHandler.networkSettings.teamNumber = networkSettings.team_number
        self.runtimeHandler.networkSettings.name = networkSettings.network_table
        self.ntClient.NT_TABLE = networkSettings.network_table
        warn(
            "Changes to team number and NetworkTables config will only take affect after restarting the runtime"
        )
        self.runtimeHandler.save()

    def close(self):
        self.runtimeHandler.running.clear()
        self.cleanup()

    @staticmethod
    def createAndRunRuntime(root: Path) -> None:
        handler = RuntimeManager(root)
        s = Synapse()
        if s.init(handler, root / "config" / "settings.yml"):
            s.run()
        s.close()
