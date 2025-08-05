# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
import importlib
import importlib.util
import os
import subprocess
import threading
import time
import traceback
from pathlib import Path
from typing import Any, List, Optional

import psutil
from synapse_net.nt_client import NtClient
from synapse_net.proto.v1 import (DeviceInfoProto, MessageProto,
                                  MessageTypeProto, PipelineProto,
                                  PipelineTypeProto,
                                  SetDefaultPipelineMessageProto,
                                  SetNetworkSettingsProto,
                                  SetPipelineIndexMessageProto,
                                  SetPipelineNameMessageProto,
                                  SetPipleineSettingMessageProto)
from synapse_net.socketServer import (SocketEvent, WebSocketServer,
                                      createMessage)

from synapse_net import devicenetworking

from ..bcolors import MarkupColors
from ..hardware.deviceactions import reboot, restartRuntime
from ..hardware.metrics import Platform
from ..log import err, log, logs, missingFeature, warn
from ..stypes import CameraID, PipelineID
from ..util import getIP, resolveGenericArgument
from .camera_factory import SynapseCamera, cameraToProto
from .config import Config, NetworkConfig
from .global_settings import GlobalSettings
from .pipeline import Pipeline, pipelineToProto
from .runtime_handler import RuntimeManager
from .settings_api import (protoToSettingValue, settingsToProto,
                           settingValueToProto)


class UIHandle:
    @staticmethod
    def isPIDRunning(pid):
        # Example implementation; replace with your actual method
        import os

        try:
            os.kill(pid, 0)
        except OSError:
            return False
        else:
            return True

    @staticmethod
    def startUI():
        spec = importlib.util.find_spec("synapse_ui")
        if spec and spec.origin:
            file_path = Path("./.uistart")
            if not file_path.exists():
                file_path.touch()

            with open(file_path, "r+") as f:
                content = f.read().strip()
                pid = int(content) if content.isdigit() else None

                if pid and UIHandle.isPIDRunning(pid):
                    os.kill(pid, 1)
                f.seek(0)
                f.truncate()
                print(f"Starting serve in directory: {Path(spec.origin).parent}")
                proc = subprocess.Popen(
                    ["serve", "."],
                    cwd=Path(spec.origin).parent,
                    start_new_session=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                log(f"Started UI at: https://{getIP()}:3000")
                f.write(str(proc.pid))


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
        self.isRunning: bool = False
        self.runtime_handler: RuntimeManager

    def init(
        self,
        runtime_handler: RuntimeManager,
        config_path: Path,
    ) -> bool:
        """
        Initializes the Synapse pipeline by loading configuration settings and setting up NetworkTables and global settings.

        Args:
            runtime_handler (RuntimeManager): The handler responsible for managing the pipeline's lifecycle.
            config_path (str, optional): The path to the configuration file. Defaults to "./config/settings.yml".

        Returns:
            bool: True if initialization was successful, False otherwise.
        """
        self.isRunning = True
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

        self.runtime_handler = runtime_handler
        self.setupRuntimeCallbacks()

        self.setupWebsocket()

        if config_path.exists():
            ...
        else:
            log("No config file!")
            with open(config_path, "w") as _:
                ...
        try:
            config = Config()
            config.load(filePath=config_path)
            self.runtime_handler.networkSettings = config.network

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
                self.runtime_handler.setup(Path(os.getcwd()))
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
        self.nt_client = NtClient()
        setup_good = self.nt_client.setup(
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
        self.runtime_handler.run()

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

            deviceInfo: DeviceInfoProto = DeviceInfoProto()
            deviceInfo.ip = getIP()

            deviceInfo.platform = (
                metrics.Platform.getCurrentPlatform().getOSType().value
            )
            deviceInfo.hostname = self.runtime_handler.networkSettings.hostname
            deviceInfo.network_interfaces.extend(psutil.net_if_addrs().keys())

            await self.websocket.sendToClient(
                ws,
                createMessage(
                    MessageTypeProto.SEND_DEVICE_INFO,
                    deviceInfo,
                ),
            )

            while not self.runtime_handler.isSetup:
                try:
                    time.sleep(0.1)
                except Exception:
                    ...

            for (
                id,
                pipeline,
            ) in self.runtime_handler.pipelineLoader.pipelineInstanceBindings.items():
                msg = pipelineToProto(pipeline, id)

                await self.websocket.sendToAll(
                    createMessage(MessageTypeProto.ADD_PIPELINE, msg)
                )

            typeMessages: List[PipelineTypeProto] = []
            for (
                typename,
                type,
            ) in self.runtime_handler.pipelineLoader.pipelineTypes.items():
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

            for id, camera in self.runtime_handler.cameraHandler.cameras.items():
                msg = cameraToProto(
                    id,
                    camera.name,
                    camera,
                    self.runtime_handler.pipelineBindings.get(id, 0),
                    self.runtime_handler.pipelineLoader.defaultPipelineIndexes.get(
                        id, -1
                    ),
                )

                await self.websocket.sendToAll(
                    createMessage(MessageTypeProto.ADD_CAMERA, msg)
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

        # Only join if not current thread
        if self.websocketThread is not threading.current_thread():
            self.websocketThread.join(timeout=5)

    def setupRuntimeCallbacks(self):
        def onAddPipeline(id: PipelineID, inst: Pipeline) -> None:
            pipelineProto = pipelineToProto(inst, id)

            Synapse.kInstance.websocket.sendToAllSync(
                createMessage(MessageTypeProto.ADD_PIPELINE, pipelineProto)
            )

        def onAddCamera(cameraid: CameraID, name: str, camera: SynapseCamera) -> None:
            cameraProto = cameraToProto(
                cameraid,
                name,
                camera,
                self.runtime_handler.pipelineBindings.get(cameraid, 0),
                self.runtime_handler.pipelineLoader.defaultPipelineIndexes.get(
                    cameraid, 0
                ),
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
                    pipeline_index=Synapse.kInstance.runtime_handler.pipelineBindings[
                        cameraIndex
                    ],
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
                Synapse.kInstance.runtime_handler.cameraHandler.getCamera(cameraIndex)
            )
            if camera:
                cameraMsg = cameraToProto(
                    cameraIndex,
                    camera.name,
                    camera,
                    pipelineIndex=self.runtime_handler.pipelineBindings[cameraIndex],
                    defaultPipeline=pipelineIndex,
                )
                msg = createMessage(MessageTypeProto.ADD_CAMERA, cameraMsg)

                Synapse.kInstance.websocket.sendToAllSync(msg)

        self.runtime_handler.pipelineLoader.onAddPipeline.add(onAddPipeline)
        self.runtime_handler.cameraHandler.onAddCamera.add(onAddCamera)
        self.runtime_handler.onSettingChangedFromNT.add(onSettingChangedInNt)
        self.runtime_handler.onPipelineChanged.add(onPipelineIndexChangedInNt)
        self.runtime_handler.pipelineLoader.onDefaultPipelineSet.add(
            onDefaultPipelineSet
        )

    def onMessage(self, ws, msg) -> None:
        msgObj = MessageProto().parse(msg)
        msgType = msgObj.type

        if msgType == MessageTypeProto.SET_SETTING:
            setSettigMSG: SetPipleineSettingMessageProto = msgObj.set_pipeline_setting
            pipeline: Optional[Pipeline] = (
                self.runtime_handler.pipelineLoader.getPipeline(
                    setSettigMSG.pipeline_index
                )
            )

            if pipeline is not None:
                val = protoToSettingValue(setSettigMSG.value)
                pipeline.setSetting(setSettigMSG.setting, val)
                self.runtime_handler.updateSetting(setSettigMSG.setting, 0, val)
        elif msgType == MessageTypeProto.SET_PIPELINE_INDEX:
            setPipeIndexMSG: SetPipelineIndexMessageProto = msgObj.set_pipeline_index
            self.runtime_handler.setPipelineByIndex(
                cameraIndex=setPipeIndexMSG.camera_index,
                pipelineIndex=setPipeIndexMSG.pipeline_index,
            )
        elif msgType == MessageTypeProto.SET_PIPELINE_NAME:
            setPipelineNameMsg: SetPipelineNameMessageProto = msgObj.set_pipeline_name
            pipeline: Optional[Pipeline] = (
                self.runtime_handler.pipelineLoader.getPipeline(
                    setPipelineNameMsg.pipeline_index
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
            addPipelineMsg: PipelineProto = msgObj.pipeline_info
            if addPipelineMsg.type is not None and (
                addPipelineMsg.type
                in self.runtime_handler.pipelineLoader.pipelineTypes.keys()
            ):
                self.runtime_handler.pipelineLoader.addPipeline(
                    index=addPipelineMsg.index,
                    name=addPipelineMsg.name,
                    typename=addPipelineMsg.type,
                    settings={
                        key: protoToSettingValue(valueProto)
                        for key, valueProto in addPipelineMsg.settings_values.items()
                    },
                )

                for (
                    cameraId,
                    pipelineId,
                ) in self.runtime_handler.pipelineBindings.items():
                    if pipelineId == addPipelineMsg.index:
                        pipeline = self.runtime_handler.pipelineLoader.getPipeline(
                            pipelineId
                        )
                        if pipeline is not None:
                            pipeline.bind(cameraId)
                        break
            else:
                err(
                    f"Cannot add pipeline of type {addPipelineMsg.type}, it is an invalid typename"
                )
        elif msgType == MessageTypeProto.DELETE_PIPELINE:
            removePipelineIndex: int = msgObj.remove_pipeline_index
            self.runtime_handler.pipelineLoader.removePipeline(removePipelineIndex)
        elif msgType == MessageTypeProto.SET_DEFAULT_PIPELINE:
            defaultPipelineMsg: SetDefaultPipelineMessageProto = (
                msgObj.set_default_pipeline
            )
            self.runtime_handler.pipelineLoader.setDefaultPipeline(
                cameraIndex=defaultPipelineMsg.camera_index,
                pipelineIndex=defaultPipelineMsg.pipeline_index,
            )
        elif msgType == MessageTypeProto.SAVE:
            self.runtime_handler.save()
        elif msgType == MessageTypeProto.SET_NETWORK_SETTINGS:
            networkSettings: SetNetworkSettingsProto = msgObj.set_network_settings
            self.setNetworkSettings(networkSettings)
        elif msgType == MessageTypeProto.REBOOT:
            self.close()
            reboot()
        elif msgType == MessageTypeProto.FORMAT:
            configFilePath = Path.cwd() / "config" / "settings.yml"
            os.remove(configFilePath)
            warn("Config file deleted! all settings will be lost")
            self.close()
            reboot()
        elif msgType == MessageTypeProto.RESTART_SYNAPSE:
            warn("Attempting to restart Synapse, may cause some unexpected results")
            self.runtime_handler.isRunning = False
            self.runtime_handler.cleanup()
            restartRuntime()

    def setNetworkSettings(self, networkSettings: SetNetworkSettingsProto) -> None:
        if Platform.getCurrentPlatform().isLinux():
            network_interfaces = []
            network_interfaces.extend(psutil.net_if_addrs().keys())

            missingFeature("Static IP doesn't work correctly at the moment")
            # if (
            #     IsValidIP(networkSettings.ip)
            #     and networkSettings.network_interface in network_interfaces
            # ):
            # if devicenetworking.setStaticIP(
            #     networkSettings.ip,
            #     networkSettings.network_interface,
            #     teamNumberToIP(networkSettings.team_number, 1),
            #     prefix_length=24,
            # ):
            #     warn(
            #         "Device wide changes to IP settings might require a restart before taking affect"
            #     )
            #
            #     self.runtime_handler.networkSettings.ip = networkSettings.ip
            #     self.runtime_handler.networkSettings.networkInterface = (
            #         networkSettings.network_interface
            #     )
            if networkSettings.ip == "NULL":  # Don't configure static IP
                self.runtime_handler.networkSettings.ip = None
            else:
                err(f"Invalid IP {networkSettings.ip} provided! Will be ignored")

            if networkSettings.hostname.__len__() > 0:
                self.runtime_handler.networkSettings.hostname = networkSettings.hostname
                devicenetworking.setHostname(networkSettings.hostname)
            else:
                err("Empty hostname isn't allowed!")
        else:
            missingFeature(
                "Non-Linux systems network and system settings modification isn't supported at the time"
            )

        self.runtime_handler.networkSettings.teamNumber = networkSettings.team_number
        self.runtime_handler.networkSettings.name = networkSettings.network_table
        self.nt_client.NT_TABLE = networkSettings.network_table
        warn(
            "Changes to team number and NetworkTables config will only take affect after restarting the runtime"
        )
        self.runtime_handler.save()

    def close(self):
        self.runtime_handler.isRunning = False
        self.cleanup()
        self.runtime_handler.cleanup()

    @staticmethod
    def createAndRunRuntime(root: Path) -> None:
        handler = RuntimeManager(root)
        s = Synapse()
        if s.init(handler, root / "config" / "settings.yml"):
            s.run()
        s.close()
