import asyncio
import os
import threading
from pathlib import Path
from typing import Any, List, Optional

from synapse_net.nt_client import NtClient
from synapse_net.proto.v1 import (DeviceInfoProto, MessageProto,
                                  MessageTypeProto, PipelineTypeProto,
                                  SetPipelineIndexMessageProto,
                                  SetPipleineSettingMessageProto)
from synapse_net.socketServer import (SocketEvent, WebSocketServer,
                                      createMessage)

from ..bcolors import MarkupColors
from ..hardware.metrics import Platform
from ..log import err, log
from ..stypes import CameraID, PipelineID
from ..util import resolveGenericArgument
from .camera_factory import SynapseCamera, cameraToProto
from .config import Config, NetworkConfig
from .global_settings import GlobalSettings
from .pipeline import Pipeline, pipelineToProto
from .runtime_handler import RuntimeManager
from .settings_api import (protoToSettingValue, settingsToProto,
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
        self.isRunning: bool = False

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
            try:
                config = Config()
                config.load(filePath=config_path)

                # Load the settings from the config file
                settings = config.getConfigMap()
                self.settings_dict = settings

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
            except Exception as e:
                log(
                    f"Something went wrong while reading settings config file. {repr(e)}"
                )
                raise e
        else:
            return False
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
            import socket

            import synapse.hardware.metrics as metrics

            deviceInfo: DeviceInfoProto = DeviceInfoProto()
            deviceInfo.ip = socket.gethostbyname(socket.gethostname())
            deviceInfo.platform = (
                metrics.Platform.getCurrentPlatform().getOSType().value
            )
            deviceInfo.hostname = socket.gethostname()
            deviceInfo.network_interfaces.extend(psutil.net_if_addrs().keys())

            await self.websocket.sendToClient(
                ws,
                createMessage(
                    MessageTypeProto.SEND_DEVICE_INFO,
                    deviceInfo,
                ),
            )

            for id, pipeline in enumerate(
                self.runtime_handler.pipelineLoader.pipelineInstanceBindings
            ):
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
                )

                await self.websocket.sendToAll(
                    createMessage(MessageTypeProto.ADD_CAMERA, msg)
                )

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
            self.websocketThread.join(timeout=5)

    def setupRuntimeCallbacks(self):
        def onAddPipeline(id: PipelineID, inst: Pipeline) -> None:
            pipelineProto = pipelineToProto(inst, id)

            self.websocket.sendToAllSync(
                createMessage(MessageTypeProto.ADD_PIPELINE, pipelineProto)
            )

        def onAddCamera(id: CameraID, name: str, camera: SynapseCamera) -> None:
            cameraProto = cameraToProto(
                id, name, camera, self.runtime_handler.pipelineBindings.get(id, 0)
            )

            self.websocket.sendToAllSync(
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

            self.websocket.sendToAllSync(msg)

        self.runtime_handler.pipelineLoader.onAddPipeline.append(onAddPipeline)
        self.runtime_handler.cameraHandler.onAddCamera.append(onAddCamera)
        self.runtime_handler.onSettingChangedFromNT.append(onSettingChangedInNt)

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

    @staticmethod
    def createAndRunRuntime(root: Path) -> None:
        handler = RuntimeManager(root)
        s = Synapse()
        if s.init(handler, root / "config" / "settings.yml"):
            s.run()
        s.cleanup()
        handler.cleanup()
