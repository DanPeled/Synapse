# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import threading
import time
from datetime import datetime
from functools import cache
from typing import Any, Dict, Final, List, Optional, Tuple

import cscore as cs
import cv2
import synapse.log as log
from synapse_net.nt_client import NtClient

from ..callback import Callback
from ..stypes import (CameraID, CameraName, CameraUID, Frame,
                      RecordingFilename, RecordingStatus, Resolution)
from .camera_factory import (CameraConfig, CameraFactory, SynapseCamera,
                             getCameraTableName)
from .global_settings import GlobalSettings


class CameraHandler:
    """
    Handles the lifecycle and operations of multiple cameras, including initialization,
    streaming, recording, and configuration based on global settings.
    """

    DEFAULT_STREAM_SIZE: Final[Tuple[int, int]] = (320, 240)
    """Default resolution (width, height) used when no specific stream size is configured."""

    def __init__(self) -> None:
        """
        Initializes empty dictionaries to hold camera instances, output streams,
        stream sizes, recording outputs, and camera configuration bindings.
        """
        self.cameras: Dict[CameraID, SynapseCamera] = {}
        self.usbCameraInfos: Dict[CameraUID, cs.UsbCameraInfo] = {}
        self.streamOutputs: Dict[CameraID, cs.CvSource] = {}
        self.streamSizes: Dict[CameraID, Resolution] = {}

        self.recordFileNames: Dict[CameraID, RecordingFilename] = {}
        self.recordingOutputs: Dict[CameraID, cv2.VideoWriter] = {}
        self.recordingResolutions: Dict[CameraID, Resolution] = {}
        self.recordingStatus: Dict[CameraID, RecordingStatus] = {}
        self.onRecordingStatusChanged: Callback[
            CameraID, RecordingStatus, RecordingFilename
        ] = Callback()

        self.cameraConfigBindings: Dict[CameraID, CameraConfig] = {}
        self.onAddCamera: Callback[CameraID, CameraName, SynapseCamera] = Callback()
        self.onRenameCamera: Callback[CameraID, CameraName] = Callback()
        self.cameraUIDs: List[CameraUID] = []

        self.cameraScanningThreadRunning: bool = True
        self.cameraScanningThread: threading.Thread

    def setRecordingStatus(
        self, cameraIndex: CameraID, status: RecordingStatus
    ) -> None:
        if cameraIndex not in self.cameras:
            log.warn(
                f"Attempted to set recording status on undefined camera #{cameraIndex}\n"
                "This status call will take affect once the camera has been added"
            )
        self.recordingStatus[cameraIndex] = status
        self.onRecordingStatusChanged.call(
            cameraIndex,
            status,
            self.recordFileNames.get(cameraIndex, "Unknown filename"),
        )

    def setup(self) -> None:
        """
        Sets up the camera system by creating cameras, generating output streams,
        and initializing recording outputs.
        """
        os.makedirs("records", exist_ok=True)
        self.createCameras()

        def cameraScanAction():
            while self.cameraScanningThreadRunning:
                self.scanCameras()
                time.sleep(10)

        self.cameraScanningThread = threading.Thread(
            target=cameraScanAction, daemon=True
        )
        self.cameraScanningThread.start()

    def createCameras(self) -> None:
        """
        Retrieves camera configuration from global settings and attempts to add
        each configured camera to the handler.
        """
        self.cameraConfigBindings = GlobalSettings.getCameraConfigMap()
        self.usbCameraInfos = {
            f"{info.name}_{info.productId}": info
            for info in cs.UsbCamera.enumerateUsbCameras()
        }

        found: List[int] = []

        for cameraIndex, cameraConfig in self.cameraConfigBindings.items():
            if len(cameraConfig.id) > 0 and cameraConfig.id not in self.cameraUIDs:
                info: Optional[cs.UsbCameraInfo] = self.usbCameraInfos.get(
                    cameraConfig.id, None
                )
                if info is not None:
                    found.append(info.productId)
                    if not (self.addCamera(cameraIndex, cameraConfig, info.dev)):
                        continue
                    else:
                        self.cameraUIDs.append(cameraConfig.id)
                else:
                    log.warn(
                        f"No camera found for product id: {cameraConfig.id} (index: {cameraIndex}), camera will be skipped"
                    )
                    continue

        self.scanCameras()

    def renameCamera(self, cameraID: CameraID, newName: CameraName) -> None:
        if cameraID in self.cameraConfigBindings:
            self.cameraConfigBindings[cameraID].name = newName
            self.cameras[cameraID].name = newName
            log.log(f"Camera #{cameraID} renamed to {newName}")
            self.onRenameCamera.call(cameraID, newName)
        else:
            log.err(
                f"Attempted to rename camera with ID {cameraID} but that camera does not exist!"
            )

    def scanCameras(self) -> None:
        self.usbCameraInfos = {
            f"{info.name}_{info.productId}": info
            for info in cs.UsbCamera.enumerateUsbCameras()
        }

        found: List[int] = []

        for info in self.usbCameraInfos.values():
            if info.productId not in found:
                found.append(info.productId)
                newIndex = 0
                if len(self.cameras.keys()) > 0:
                    newIndex = max(self.cameras.keys()) + 1
                cameraIndex = newIndex
                cameraConfig = CameraConfig(
                    name=info.name,
                    id=f"{info.name}_{info.productId}",
                    defaultPipeline=0,
                    calibration={},
                    streamRes=self.DEFAULT_STREAM_SIZE,
                )

                if cameraConfig.id not in self.cameraUIDs:
                    log.log(
                        f"Found non-registered camera: {info.name} (i={info.dev}), adding automatically"
                    )
                    GlobalSettings.setCameraConfig(cameraIndex, cameraConfig)
                    if not (self.addCamera(cameraIndex, cameraConfig, info.dev)):
                        continue
                    else:
                        self.cameraUIDs.append(cameraConfig.id)

    def getCamera(self, cameraIndex: CameraID) -> Optional[SynapseCamera]:
        """
        Retrieves a specific camera instance by its index.

        Args:
            cameraIndex (CameraID): Index of the camera to retrieve.

        Returns:
            Optional[SynapseCamera]: The camera instance if it exists, otherwise None.
        """
        return self.cameras.get(cameraIndex, None)

    def getStreamRes(self, cameraIndex: CameraID) -> Tuple[int, int]:
        """
        Retrieves the streaming resolution for the given camera index.

        If the camera configuration is available via `GlobalSettings.getCameraConfig(i)`,
        returns its configured stream resolution and updates `self.streamSizes`.
        Otherwise, returns a default resolution.

        Args:
            cameraIndex (CameraID): The index of the camera.

        Returns:
            Tuple[int, int]: The width and height of the stream resolution.
        """
        cameraConfig: Optional[CameraConfig] = GlobalSettings.getCameraConfig(
            cameraIndex
        )

        if cameraConfig is not None:
            streamRes = cameraConfig.streamRes
            self.streamSizes[cameraIndex] = streamRes
            return (streamRes[0], streamRes[1])

        return self.DEFAULT_STREAM_SIZE

    def createStreamOutput(self, cameraIndex: CameraID) -> cs.CvSource:
        """
        Initializes and returns video output streams for all configured cameras.

        For each camera index in `self.cameras`, retrieves its desired streaming resolution
        from the global camera configuration (if available), falls back to the default resolution
        otherwise, and creates a new video stream via `cs.CameraServer.putVideo`.

        Also updates `self.streamSizes` with the resolved stream resolution for each camera.

        Returns:
            dict[CameraID, cs.CameraServer.VideoOutput]: A dictionary mapping camera indices
            to their corresponding video output objects.
        """
        return cs.CameraServer.putVideo(
            f"{NtClient.NT_TABLE}/{getCameraTableName(self.cameras[cameraIndex])}",
            width=self.getStreamRes(cameraIndex)[0],
            height=self.getStreamRes(cameraIndex)[1],
        )

    @cache
    def getOutput(self, cameraIndex: CameraID) -> cs.CvSource:
        """
        Retrieves the video output stream for a specific camera.

        Args:
            cameraIndex (CameraID): The camera index.

        Returns:
            cs.CvSource: The associated video output stream.
        """
        return self.streamOutputs[cameraIndex]

    @cache
    def getRecordOutput(self, cameraIndex: CameraID) -> cv2.VideoWriter:
        """
        Retrieves the recording output writer for a specific camera.

        Args:
            cameraIndex (CameraID): The camera index.

        Returns:
            cv2.VideoWriter: The associated video writer.
        """

        assert cameraIndex in self.cameras

        if cameraIndex in self.recordingOutputs:
            return self.recordingOutputs[cameraIndex]
        fourcc = cv2.VideoWriter.fourcc(*"MJPG")

        resolution = self.cameras[cameraIndex].getResolution()

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"records/{NtClient.NT_TABLE}_camera{cameraIndex}_{timestamp}.avi"

        self.recordingOutputs[cameraIndex] = cv2.VideoWriter(
            filename=filename,
            fourcc=fourcc,
            fps=30.0,
            frameSize=resolution,
        )
        self.recordingResolutions[cameraIndex] = resolution

        log.log(
            f"Started recording camera {self.cameras[cameraIndex].name} to {filename}"
        )
        self.recordFileNames[cameraIndex] = filename

        return self.recordingOutputs[cameraIndex]

    def publishFrame(self, frame: Frame, camera: SynapseCamera) -> None:
        """
        Publishes a frame to the output stream and optionally writes it to the recording output
        if recording is enabled.

        Args:
            frame (Frame): The image frame to publish.
            camera (SynapseCamera): The camera that produced the frame.
        """
        if frame is not None:
            # Resize for display/output
            resized_frame = cv2.resize(
                frame,
                self.streamSizes[camera.cameraIndex],
                interpolation=cv2.INTER_AREA,
            )
            self.getOutput(camera.cameraIndex).putFrame(resized_frame)

            # Write to MJPEG AVI if recording
            if self.recordingStatus[camera.cameraIndex]:
                videoWriter = self.getRecordOutput(camera.cameraIndex)
                videoWriter.write(
                    cv2.resize(frame, self.recordingResolutions[camera.cameraIndex])
                )
            elif camera.cameraIndex in self.recordingOutputs:
                log.log(
                    f"Written Camera {camera.name} recording to {self.recordFileNames[camera.cameraIndex]}"
                )
                videoWriter = self.recordingOutputs.pop(camera.cameraIndex)
                videoWriter.release()

    def addCamera(
        self, cameraIndex: CameraID, cameraConfig: CameraConfig, dev: int
    ) -> bool:
        """
        Adds a camera to the handler by opening it through OpenCV.

        Args:
            cameraIndex (CameraID): Camera index to open.

        Returns:
            bool: True if the camera was successfully added, False otherwise.
        """

        try:
            camera = CameraFactory.create(
                cameraType=CameraFactory.kCameraServer,
                cameraIndex=cameraIndex,
                path=dev,
                name=f"{cameraConfig.name}",
            )
            camera.setIndex(cameraIndex)
        except Exception as e:
            log.err(f"Failed to start camera capture: {e}")
            return False

        MAX_RETRIES = 30
        for attempt in range(MAX_RETRIES):
            if camera.isConnected():
                break
            log.log(
                f"Trying to open camera {camera.name} ({cameraConfig.id}), attempt {attempt + 1}"
            )
            time.sleep(1)

        if camera.isConnected():
            self.cameras[cameraIndex] = camera
            self.streamOutputs[cameraIndex] = self.createStreamOutput(cameraIndex)
            self.setRecordingStatus(cameraIndex, False)

            self.onAddCamera.call(cameraIndex, cameraConfig.name, camera)

            log.log(
                f"Camera (name={cameraConfig.name}, id={cameraConfig.id}, id={cameraIndex}) added successfully."
            )
            return True

        log.err(
            f"Failed to open camera {camera.name} ({cameraConfig.id}) after {MAX_RETRIES} retries."
        )
        return False

    def setCameraProps(
        self, settings: Dict[str, Any], camera: SynapseCamera
    ) -> Dict[str, Any]:
        """
        Applies the specified settings to a camera and sets its video mode.

        Args:
            settings (Dict[str, Any]): Dictionary of property names and values to apply.
            camera (SynapseCamera): The camera to configure.

        Returns:
            Dict[str, Any]: Dictionary of updated settings (currently unused).
        """
        updated_settings = {}
        for settingName in settings.keys():
            setting_value = settings.get(settingName)
            if setting_value is not None:
                camera.setProperty(
                    prop=settingName,
                    value=setting_value,
                )

        return updated_settings

    def cleanup(self) -> None:
        """
        Releases all video writers and closes all active camera connections.
        """
        self.cameraScanningThreadRunning = False
        self.cameraScanningThread.join()

        for record in self.recordingOutputs.values():
            record.release()
        for camera in self.cameras.values():
            camera.close()
