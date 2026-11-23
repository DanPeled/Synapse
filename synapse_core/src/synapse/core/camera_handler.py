# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later
import os
import queue
import sys
import threading
import time
import traceback
from dataclasses import dataclass
from datetime import datetime
from itertools import chain
from typing import Any, Dict, Final, List, Optional, Tuple, Type, Union

import cscore as cs
import cv2
import numpy as np
import synapse.log as log
from ntcore import EventFlags, NetworkTableEntry, NetworkTableInstance
from synapse_net.nt_client import NtClient

from ..callback import Callback
from ..stypes import (
    CameraID,
    CameraName,
    CameraUID,
    Frame,
    RecordingFilename,
    RecordingStatus,
    Resolution,
)
from .camera.camera_handle import CameraHandle
from .camera.no_signal import NoSignalCamera, generateNoSignalFrame
from .camera.synapse_camera import SynapseCamera
from .camera_factory import (
    CameraConfig,
    CameraFactory,
    getCameraTableName,
    invalidateCameraTable,
)
from .global_settings import GlobalSettings
from .lifecycle import joinThread


@dataclass
class FPSView:
    font = cv2.FONT_HERSHEY_PLAIN
    fontScale = 3
    thickness = 2
    color = (0, 256, 0)
    position = (10, 30)


UsbCameraInfos = Dict[CameraUID, cs.UsbCameraInfo]
UsbDeviceSignature = Tuple[Tuple[str, int, int], ...]
UsbInfoSignature = Tuple[Tuple[CameraUID, str, str, Tuple[str, ...], int, int], ...]


class _PublishLane:
    """Bounded, newest-first handoff from a camera loop to its stream sink."""

    def __init__(self, cameraIndex: CameraID, publish) -> None:
        self.cameraIndex = cameraIndex
        self._publish = publish
        self.frames: "queue.Queue[Tuple[np.ndarray, bool, int, Optional[int]]]" = (
            queue.Queue(maxsize=1)
        )
        self.stopEvent = threading.Event()
        self._frameReady = threading.Event()
        self.thread = threading.Thread(
            target=self._run,
            daemon=True,
            name=f"StreamPublisher-{cameraIndex}",
        )

        self._lock = threading.Lock()
        self._free: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=2)
        self._buffers: List[np.ndarray] = []
        self._shape: Optional[Tuple[int, ...]] = None
        self._dtype: Optional[np.dtype] = None
        self._generation = 0
        self.dropped = 0

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.stopEvent.set()
        self._frameReady.set()
        self.thread.join(timeout=1.0)

    def _acquire(self, frame: Frame) -> Tuple[np.ndarray, bool, int]:
        shape = tuple(frame.shape)
        dtype = frame.dtype
        with self._lock:
            if shape != self._shape or dtype != self._dtype:
                self._generation += 1
                self._shape = shape
                self._dtype = dtype
                self._buffers = [np.empty(shape, dtype=dtype) for _ in range(2)]
                while not self._free.empty():
                    self._free.get_nowait()
                for buffer in self._buffers:
                    self._free.put_nowait(buffer)

            generation = self._generation
            try:
                return self._free.get_nowait(), True, generation
            except queue.Empty:
                # A resize can leave both pooled buffers in flight. A one-off
                # copy is cheaper than blocking the camera loop.
                return frame.copy(), False, generation

    def _release(self, buffer: np.ndarray, pooled: bool, generation: int) -> None:
        if not pooled:
            return
        with self._lock:
            if generation == self._generation:
                try:
                    self._free.put_nowait(buffer)
                except queue.Full:
                    pass

    def enqueue(self, frame: Frame, fps: Optional[int]) -> None:
        # If a frame is already queued, replace it and reuse its buffer. This
        # avoids taking a second buffer from the pool when the lane is behind,
        # which would otherwise force a one-off full-frame allocation.
        buffer: Optional[np.ndarray] = None
        pooled = False
        generation = 0
        try:
            staleBuffer, stalePooled, staleGeneration, _ = self.frames.get_nowait()
        except queue.Empty:
            pass
        else:
            with self._lock:
                self.dropped += 1
            if staleBuffer.shape == frame.shape and staleBuffer.dtype == frame.dtype:
                buffer = staleBuffer
                pooled = stalePooled
                generation = staleGeneration
            else:
                self._release(staleBuffer, stalePooled, staleGeneration)

        if buffer is None:
            buffer, pooled, generation = self._acquire(frame)

        np.copyto(buffer, frame)
        item = (buffer, pooled, generation, fps)

        try:
            self.frames.put_nowait(item)
            self._frameReady.set()
        except queue.Full:
            self._release(buffer, pooled, generation)
            with self._lock:
                self.dropped += 1

    def stats(self) -> Dict[str, int]:
        with self._lock:
            dropped = self.dropped
        return {"queued": self.frames.qsize(), "dropped": dropped}

    def resetStats(self) -> None:
        with self._lock:
            self.dropped = 0

    def _run(self) -> None:
        while not self.stopEvent.is_set():
            # Event wait avoids the 200 ms idle wakeup while still draining every
            # frame already queued when the lane was busy.
            self._frameReady.wait(0.2)
            self._frameReady.clear()

            while not self.stopEvent.is_set():
                try:
                    buffer, pooled, generation, fps = self.frames.get_nowait()
                except queue.Empty:
                    break

                try:
                    self._publish(buffer, fps)
                except Exception:
                    pass
                finally:
                    self._release(buffer, pooled, generation)


def _getUsbDeviceSignature() -> Optional[UsbDeviceSignature]:
    """Reads a cheap signature of video device nodes, or None if unsupported.

    Linux exposes USB hotplug as ``/dev/video*`` entries; watching their names
    and identities detects add/remove events without enumerating cameras.
    Other platforms have no equivalent portable signal and use the adaptive
    enumeration-based fallback in ``CameraHandler._checkForCameraChanges``.
    """
    if not sys.platform.startswith("linux"):
        return None

    devices = []
    try:
        with os.scandir("/dev") as entries:
            for entry in entries:
                if not entry.name.startswith("video"):
                    continue
                try:
                    stat = entry.stat(follow_symlinks=False)
                except OSError:
                    # A device can disappear between scandir and stat.
                    continue
                devices.append((entry.name, stat.st_rdev, stat.st_ino))
    except OSError:
        return None

    return tuple(sorted(devices))


class CameraHandler:
    """
    Handles the lifecycle and operations of multiple cameras, including initialization,
    streaming, recording, and configuration based on global settings.
    """

    DEFAULT_STREAM_SIZE: Final[Tuple[int, int]] = (320, 240)
    """Default resolution (width, height) used when no specific stream size is configured."""

    # INTER_AREA is a good downscaling filter, but it is an order of magnitude
    # slower than INTER_LINEAR for the large reductions used by live streams
    # (for example 1920x1080 -> 320x240). The preview is transient, so prefer
    # the much cheaper filter there and keep INTER_AREA for recorded frames.
    STREAM_INTERPOLATION: Final[int] = cv2.INTER_LINEAR

    DEFAULT_CHANGE_POLL_INTERVAL: Final[float] = 0.25
    """How often platforms with a device-node signal check for hotplug changes."""

    DEFAULT_SCAN_MIN_INTERVAL: Final[float] = 1.0
    """Initial fallback probe interval on platforms without a device signal."""

    DEFAULT_SCAN_MAX_INTERVAL: Final[float] = 30.0
    """Upper bound for the adaptive fallback probe interval while stable."""

    def __init__(self) -> None:
        """
        Initializes empty dictionaries to hold camera instances, output streams,
        stream sizes, recording outputs, and camera configuration bindings.
        """
        self.cameraHandles: Dict[CameraID, CameraHandle] = {}
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
        self.onAddCamera: Callback[CameraID, CameraName, CameraHandle] = Callback()
        self.onRenameCamera: Callback[CameraID, CameraName] = Callback()
        self.onCameraStreamChanged: Callback[CameraID, CameraHandle] = Callback()
        self._streamListeners: Dict[CameraID, int] = {}
        self._streamTopics: Dict[CameraID, str] = {}
        self.cameraUIDs: List[CameraUID] = []
        self.requestedCameraUIDs: Dict[CameraUID, CameraID] = {}
        self.cameraType: Type[SynapseCamera] = CameraFactory.kDefault

        self.lastPublishTime: Dict[CameraID, float] = {}
        self.publishInterval: float = 1.0 / 30.0

        # Reusable resize destinations, keyed by camera. Streaming resizes every
        # captured frame, so allocating a new output image per frame shows up in
        # profiles; these buffers let `cv2.resize` write in place instead.
        self._streamFrameBuffers: Dict[CameraID, np.ndarray] = {}
        self._recordFrameBuffers: Dict[CameraID, np.ndarray] = {}

        # Stream and recording writers run on their own bounded lane per camera.
        # A slow CvSource or VideoWriter must never stall pipeline throughput.
        self._publishLanes: Dict[CameraID, _PublishLane] = {}
        self._publishingEnabled = True

        self.cameraScanningThread: threading.Thread

        self.stopCameraScanEvent = threading.Event()
        self._cameraScanRequested = threading.Event()
        self._pendingUsbCameraInfos: Optional[UsbCameraInfos] = None
        self._lastDeviceSignature: Optional[UsbDeviceSignature] = None
        self._lastUsbInfoSignature: UsbInfoSignature = ()

        # Timing is instance state so tests can drive the scanner deterministically.
        self.cameraChangePollInterval: float = self.DEFAULT_CHANGE_POLL_INTERVAL
        self.cameraScanMinInterval: float = self.DEFAULT_SCAN_MIN_INTERVAL
        self.cameraScanMaxInterval: float = self.DEFAULT_SCAN_MAX_INTERVAL
        self._cameraProbeInterval: float = self.cameraScanMinInterval

    def setRecordingStatus(
        self, cameraIndex: CameraID, status: RecordingStatus
    ) -> None:
        if cameraIndex not in self.cameraHandles:
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

    def setCameraType(self, cameraType: Type[SynapseCamera]) -> None:
        """Selects the camera implementation used to create configured cameras."""
        self.cameraType = cameraType

    def setup(self) -> None:
        """
        Sets up the camera system by creating cameras, generating output streams,
        and initializing recording outputs.
        """
        os.makedirs("records", exist_ok=True)
        self.createCameras()

        if self.cameraType is not CameraFactory.kDefault:
            # Non-USB backends produce their cameras from configuration only.
            return

        def cameraScanAction() -> None:
            while not self.stopCameraScanEvent.is_set():
                if not self._waitForCameraChange():
                    break
                if self.stopCameraScanEvent.is_set():
                    break
                usbCameraInfos = self._pendingUsbCameraInfos
                self._pendingUsbCameraInfos = None
                self.scanCameras(usbCameraInfos=usbCameraInfos)

        self.cameraScanningThread = threading.Thread(
            target=cameraScanAction, daemon=True, name="Camera scanner"
        )
        self.cameraScanningThread.start()

    def requestCameraScan(self) -> None:
        """Wakes the scanner for one full rescan, e.g. after a config change."""
        if self.cameraType is not CameraFactory.kDefault:
            return
        self._cameraScanRequested.set()

    def _waitForCameraChange(self) -> bool:
        """Waits for a detected camera change or an explicit scan request."""
        while not self.stopCameraScanEvent.is_set():
            if self._checkForCameraChanges():
                return True
            self._cameraScanRequested.wait(self._cameraProbeInterval)
        return False

    def _checkForCameraChanges(self) -> bool:
        """Checks for hotplug changes without running a side-effecting rescan.

        Returns True when ``scanCameras()`` should run. Platforms with a device
        node signal need only compare that signature; other platforms compare
        a lightweight camera enumeration and back off adaptively while stable.
        """
        if self._cameraScanRequested.is_set():
            self._cameraScanRequested.clear()
            self._pendingUsbCameraInfos = None
            return True

        deviceSignature = _getUsbDeviceSignature()
        if deviceSignature is not None:
            self._cameraProbeInterval = self.cameraChangePollInterval
            if self._lastDeviceSignature is None:
                self._lastDeviceSignature = deviceSignature
            elif deviceSignature != self._lastDeviceSignature:
                self._lastDeviceSignature = deviceSignature
                return True
            return False

        usbCameraInfos = self._enumerateUsbCameras()
        infoSignature = self._usbInfoSignature(usbCameraInfos)
        if infoSignature != self._lastUsbInfoSignature:
            self._lastUsbInfoSignature = infoSignature
            self._pendingUsbCameraInfos = usbCameraInfos
            self._cameraProbeInterval = self.cameraScanMinInterval
            return True

        self._cameraProbeInterval = min(
            self._cameraProbeInterval * 2, self.cameraScanMaxInterval
        )
        return False

    @staticmethod
    def _enumerateUsbCameras() -> UsbCameraInfos:
        return {
            f"{info.name}_{info.productId}": info
            for info in cs.UsbCamera.enumerateUsbCameras()
        }

    @staticmethod
    def _usbInfoSignature(infos: UsbCameraInfos) -> UsbInfoSignature:
        return tuple(
            sorted(
                (
                    uid,
                    str(info.dev),
                    str(info.path),
                    tuple(str(path) for path in getattr(info, "otherPaths", ()) or ()),
                    int(info.productId),
                    int(info.vendorId),
                )
                for uid, info in infos.items()
            )
        )

    def createCameras(self) -> None:
        """
        Retrieves camera configuration from global settings and attempts to add
        each configured camera to the handler.
        """
        self.cameraConfigBindings = GlobalSettings.getCameraConfigMap()

        if self.cameraType is not CameraFactory.kDefault:
            # Non-USB backends create one camera per configured index; the
            # camera index is the identity, so no USB-style UID matching.
            for cameraIndex, cameraConfig in self.cameraConfigBindings.items():
                self.addCamera(cameraIndex, cameraConfig, cameraIndex)
            return

        self.usbCameraInfos = self._enumerateUsbCameras()

        for cameraIndex, cameraConfig in self.cameraConfigBindings.items():
            if len(cameraConfig.id) > 0 and cameraConfig.id not in self.cameraUIDs:
                info: Optional[cs.UsbCameraInfo] = self.usbCameraInfos.get(
                    cameraConfig.id, None
                )
                if info is not None:
                    if not (self.addCamera(cameraIndex, cameraConfig, info.dev)):
                        continue
                    else:
                        self.cameraUIDs.append(cameraConfig.id)
                else:
                    self.requestedCameraUIDs[cameraConfig.id] = cameraIndex

                    self.addCameraData(
                        cameraIndex,
                        cameraConfig,
                        CameraHandle(
                            NoSignalCamera(),
                            cameraConfig.name,
                            cameraIndex,
                        ),
                    )

                    log.warn(
                        f"No camera found for product id: {cameraConfig.id} (index: {cameraIndex}), camera will be skipped and added later"
                    )
                    continue

        # The initial scan reuses the map collected above; only changes or
        # explicit requests trigger another enumeration after startup.
        self.scanCameras(usbCameraInfos=self.usbCameraInfos)

    def renameCamera(self, cameraID: CameraID, newName: CameraName) -> None:
        if cameraID not in self.cameraConfigBindings:
            log.err(
                f"Attempted to rename camera with ID {cameraID} but that camera does not exist!"
            )
            return

        handle = self.cameraHandles[cameraID]
        oldSourceName = f"{NtClient.NT_TABLE}/{getCameraTableName(handle)}"
        nameChanged = getCameraTableName(handle) != newName

        self._unregisterStreamListener(cameraID)
        self.cameraConfigBindings[cameraID].name = newName
        handle.name = newName
        invalidateCameraTable(handle)

        if nameChanged:
            # CSCore stream sources keep the name they were created with. Move
            # the source to the new NT path so settings and streams stay together.
            handle.stream = ""
            try:
                cs.CameraServer.removeCamera(oldSourceName)
            except Exception as error:
                log.warn(f"Failed to remove old stream source {oldSourceName}: {error}")
            self.streamOutputs[cameraID] = self.createStreamOutput(cameraID)
            frame = generateNoSignalFrame(handle.name, handle.cameraIndex)
            if frame is not None:
                self.streamOutputs[cameraID].putFrame(frame)

        self._registerStreamListener(cameraID)

        log.info(f"Camera #{cameraID} renamed to {newName}")
        self.onRenameCamera.call(cameraID, newName)

    def scanCameras(self, usbCameraInfos: Optional[UsbCameraInfos] = None) -> None:
        """Runs a full camera scan, optionally with a pre-collected camera map.

        Args:
            usbCameraInfos: USB camera map collected by the caller. When None,
                cameras are enumerated here (e.g. for an explicit rescan).
        """
        if usbCameraInfos is None:
            usbCameraInfos = self._enumerateUsbCameras()

        self.usbCameraInfos = usbCameraInfos
        self._lastUsbInfoSignature = self._usbInfoSignature(usbCameraInfos)
        self._lastDeviceSignature = _getUsbDeviceSignature()
        self._cameraProbeInterval = self.cameraScanMinInterval
        self._pendingUsbCameraInfos = None

        found: List[int] = []

        for info in self.usbCameraInfos.values():
            id = f"{info.name}_{info.productId}"
            if info.productId not in found and id not in self.cameraUIDs:
                found.append(info.productId)
                newIndex = 0

                if len(self.requestedCameraUIDs.keys()) > 0:
                    if id in self.requestedCameraUIDs.keys():
                        newIndex = self.requestedCameraUIDs.pop(id)
                    else:
                        newIndex = (
                            max(
                                chain(
                                    self.requestedCameraUIDs.values(),
                                    self.cameraHandles.keys(),
                                )
                            )
                            + 1
                        )
                else:
                    m = max(self.cameraHandles.keys(), default=-1)
                    newIndex = m + 1

                cameraIndex = newIndex
                cameraConfig = CameraConfig(
                    name=info.name,
                    id=id,
                    defaultPipeline=0,
                    calibration={},
                    streamRes=self.DEFAULT_STREAM_SIZE,
                )

                if cameraConfig.id not in self.cameraUIDs:
                    log.info(
                        f"Found non-registered camera: {info.name} (i={cameraIndex}), adding automatically"
                    )
                    GlobalSettings.setCameraConfig(cameraIndex, cameraConfig)
                    if not (self.addCamera(cameraIndex, cameraConfig, info.dev)):
                        continue
                    else:
                        self.cameraUIDs.append(cameraConfig.id)

    def getCameraHandle(self, cameraIndex: CameraID) -> Optional[CameraHandle]:
        """
        Retrieves a specific camera instance by its index.

        Args:
            cameraIndex (CameraID): Index of the camera to retrieve.

        Returns:
            Optional[CameraHandle]: The camera instance if it exists, otherwise None.
        """
        return self.cameraHandles.get(cameraIndex, None)

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
        assert cameraIndex in self.cameraHandles

        return cs.CameraServer.putVideo(
            name=f"{NtClient.NT_TABLE}/{getCameraTableName(self.cameraHandles[cameraIndex])}",
            width=self.getStreamRes(cameraIndex)[0],
            height=self.getStreamRes(cameraIndex)[1],
        )

    @staticmethod
    def _streamTopicName(handle: CameraHandle) -> str:
        """Topic CSCore publishes the camera's stream URLs to."""
        return (
            f"/CameraPublisher/{NtClient.NT_TABLE}/{getCameraTableName(handle)}/streams"
        )

    @staticmethod
    def _parseStreamUrl(streams: Any) -> str:
        """Extract a usable stream URL from a NetworkTables value.

        CSCore publishes a string array and historically the second entry has
        been used, but the array can be empty, short, or contain non-string
        values while a camera is starting up. Malformed data is ignored rather
        than raising out of the NT listener callback.
        """
        if not isinstance(streams, (list, tuple)):
            return ""

        candidates = list(streams)
        if len(candidates) > 1:
            candidates.insert(0, candidates[1])

        for candidate in candidates:
            if not isinstance(candidate, str):
                continue
            url = candidate.replace("mjpg:", "", 1)
            if url.startswith(("http://", "https://")):
                return url
        return ""

    def _getStreamsEntry(self, cameraIndex: CameraID) -> NetworkTableEntry:
        handle = self.cameraHandles[cameraIndex]
        return (
            NetworkTableInstance.getDefault()
            .getTable("CameraPublisher")
            .getSubTable(NtClient.NT_TABLE)
            .getSubTable(getCameraTableName(handle))
            .getEntry("streams")
        )

    def _unregisterStreamListener(self, cameraIndex: CameraID) -> None:
        listener = self._streamListeners.pop(cameraIndex, None)
        self._streamTopics.pop(cameraIndex, None)
        if listener is None:
            return
        try:
            NetworkTableInstance.getDefault().removeListener(listener)
        except Exception as error:
            log.warn(
                f"Failed to remove streams listener for camera #{cameraIndex}: {error}"
            )

    def _registerStreamListener(self, cameraIndex: CameraID) -> None:
        """Watch the camera's streams topic without blocking camera setup."""
        self._unregisterStreamListener(cameraIndex)

        handle = self.cameraHandles[cameraIndex]
        topicName = self._streamTopicName(handle)
        self._streamTopics[cameraIndex] = topicName

        def onStreamsChanged(event: Any, topicName=topicName) -> None:
            # Ignore callbacks from a listener that was replaced by a rename.
            if self._streamTopics.get(cameraIndex) != topicName:
                return
            try:
                streams = event.data.value.getStringArray()
            except Exception:
                return
            stream = self._parseStreamUrl(streams)
            current = self.cameraHandles.get(cameraIndex)
            if not stream or current is None or current.stream == stream:
                return
            current.stream = stream
            self.onCameraStreamChanged.call(cameraIndex, current)

        try:
            listener = NetworkTableInstance.getDefault().addListener(
                self._getStreamsEntry(cameraIndex),
                EventFlags.VALUE_ALL | EventFlags.IMMEDIATE | EventFlags.PUBLISH,
                onStreamsChanged,
            )
        except Exception as error:
            log.warn(
                f"Failed to watch streams topic for camera #{cameraIndex}: {error}"
            )
            return
        self._streamListeners[cameraIndex] = listener

    def getOutput(self, cameraIndex: CameraID) -> cs.CvSource:
        """
        Retrieves the video output stream for a specific camera.

        Args:
            cameraIndex (CameraID): The camera index.

        Returns:
            cs.CvSource: The associated video output stream.
        """
        return self.streamOutputs[cameraIndex]

    def getRecordOutput(self, cameraIndex: CameraID) -> cv2.VideoWriter:
        """
        Retrieves the recording output writer for a specific camera.

        Args:
            cameraIndex (CameraID): The camera index.

        Returns:
            cv2.VideoWriter: The associated video writer.
        """

        if cameraIndex not in self.cameraHandles:
            raise KeyError(f"Camera {cameraIndex} not found")

        if cameraIndex in self.recordingOutputs:
            return self.recordingOutputs[cameraIndex]
        fourcc = cv2.VideoWriter.fourcc(*"mp4v")  # efficient MP4 codec

        try:
            resolution = self.cameraHandles[cameraIndex].camera.getResolution()
        except Exception:
            resolution = self.streamSizes.get(cameraIndex, (640, 480))

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        try:
            nt_table_name = NtClient.NT_TABLE
        except Exception:
            nt_table_name = "Synapse"
        filename = f"records/{nt_table_name}_camera{cameraIndex}_{timestamp}.mp4"

        self.recordingOutputs[cameraIndex] = cv2.VideoWriter(
            filename=filename,
            fourcc=fourcc,
            fps=30.0,
            frameSize=resolution,
        )
        self.recordingResolutions[cameraIndex] = resolution

        try:
            log.info(
                f"Started recording camera {self.cameraHandles[cameraIndex].name} to {filename}",
                shouldAlert=True,
            )
        except Exception:
            pass
        self.recordFileNames[cameraIndex] = filename

        return self.recordingOutputs[cameraIndex]

    def _resizeFrame(
        self,
        frame: Frame,
        size: Resolution,
        buffers: Dict[CameraID, np.ndarray],
        cameraIndex: CameraID,
        interpolation: int = cv2.INTER_AREA,
    ) -> Frame:
        """
        Resizes `frame` to `size`, reusing a per-camera destination buffer.

        Frames are already allocated by the camera handle buffer pool, so an
        extra allocation (and copy) for every published frame is avoidable.
        When the frame is already at the requested size no work is done at all.

        Args:
            frame (Frame): Source frame.
            size (Resolution): Target (width, height).
            buffers (Dict[CameraID, np.ndarray]): Destination cache to use.
            cameraIndex (CameraID): Camera the frame belongs to.
            interpolation (int): OpenCV interpolation flag for the resize.

        Returns:
            Frame: The resized frame (or `frame` itself if no resize is needed).
        """
        width, height = int(size[0]), int(size[1])

        if frame.shape[1] == width and frame.shape[0] == height:
            return frame

        destination = buffers.get(cameraIndex)
        if (
            destination is None
            or destination.shape[0] != height
            or destination.shape[1] != width
            or destination.dtype != frame.dtype
        ):
            destination = np.empty((height, width) + frame.shape[2:], dtype=frame.dtype)
            buffers[cameraIndex] = destination

        return cv2.resize(
            frame,
            (width, height),
            dst=destination,
            interpolation=interpolation,
        )

    def _startPublishLane(self, cameraIndex: CameraID) -> _PublishLane:
        lane = _PublishLane(
            cameraIndex,
            lambda frame, fps, index=cameraIndex: self._publishFrameSync(
                frame, self.cameraHandles[index], fps
            ),
        )
        self._publishLanes[cameraIndex] = lane
        lane.start()
        return lane

    def setPublishingEnabled(self, enabled: bool) -> None:
        """Enable or disable stream/record publication without stopping cameras."""
        self._publishingEnabled = bool(enabled)

    def publishFrame(
        self, frame: Frame, handle: CameraHandle, fps: Optional[int] = None
    ) -> None:
        """Hand a throttled frame to the camera's stream/record lane.

        The camera processing thread only copies into a pooled buffer and never
        waits on ``CvSource.putFrame`` or ``VideoWriter.write``. When the lane
        is behind, the stale queued frame is replaced so latency stays bounded.
        """
        assert frame is not None
        if not self._publishingEnabled:
            return

        now = time.perf_counter()
        cameraIndex = handle.cameraIndex

        lastTime = self.lastPublishTime.get(cameraIndex, 0.0)
        if now - lastTime < self.publishInterval:
            return
        self.lastPublishTime[cameraIndex] = now

        lane = self._publishLanes.get(cameraIndex)
        if lane is None:
            # Tests and headless callers can publish without a managed camera.
            self._publishFrameSync(frame, handle, fps)
            return
        lane.enqueue(frame, fps)

    @staticmethod
    def _drawFps(frame: Frame, fps: Optional[int]) -> None:
        """Draw the FPS overlay on an already-resized stream frame."""
        if fps is None:
            return

        # Scaling the text with the output height keeps the overlay readable on
        # a small preview without paying for a full-resolution text draw first.
        scale = min(FPSView.fontScale, max(0.5, frame.shape[0] / 720.0 * FPSView.fontScale))
        thickness = 2 if scale >= 2.0 else 1
        position = (10, max(12, int(30 * scale / FPSView.fontScale)))
        try:
            cv2.putText(
                frame,
                f"FPS: {int(fps)}",
                position,
                FPSView.font,
                scale,
                FPSView.color,
                thickness,
                lineType=cv2.LINE_8,
            )
        except Exception:
            pass

    def _publishFrameSync(
        self, frame: Frame, handle: CameraHandle, fps: Optional[int] = None
    ) -> None:
        """Resize and write a frame; called on the per-camera publication lane."""
        cameraIndex = handle.cameraIndex

        streamSize = self.streamSizes.get(cameraIndex)
        if streamSize is None:
            streamSize = self.getStreamRes(cameraIndex)
        streamFrame = self._resizeFrame(
            frame,
            streamSize,
            self._streamFrameBuffers,
            cameraIndex,
            interpolation=self.STREAM_INTERPOLATION,
        )
        self._drawFps(streamFrame, fps)
        self.getOutput(cameraIndex).putFrame(streamFrame)

        if self.recordingStatus.get(cameraIndex, False):
            videoWriter = self.getRecordOutput(cameraIndex)
            recordRes = self.recordingResolutions.get(cameraIndex)
            if recordRes is None:
                recordRes = self.cameraHandles[cameraIndex].camera.getResolution()
                self.recordingResolutions[cameraIndex] = recordRes
            recordFrame = self._resizeFrame(
                frame, recordRes, self._recordFrameBuffers, cameraIndex
            )
            # When the stream frame was the source frame, a resized recording
            # already contains the overlay; drawing again would double it.
            if recordFrame is not streamFrame and streamFrame is not frame:
                self._drawFps(recordFrame, fps)
            videoWriter.write(recordFrame)

        elif cameraIndex in self.recordingOutputs:
            log.info(
                f"Written Camera {handle.name} recording to {self.recordFileNames[cameraIndex]}",
                shouldAlert=True,
            )
            videoWriter = self.recordingOutputs.pop(cameraIndex)
            videoWriter.release()
            self._recordFrameBuffers.pop(cameraIndex, None)

    def getPublishStats(self, cameraIndex: Optional[CameraID] = None) -> Dict[str, int]:
        """Return bounded-lane queue depth and dropped-frame counters."""
        if cameraIndex is not None:
            lane = self._publishLanes.get(cameraIndex)
            return {"queued": 0, "dropped": 0} if lane is None else lane.stats()

        totals = {"queued": 0, "dropped": 0}
        for lane in self._publishLanes.values():
            stats = lane.stats()
            totals["queued"] += stats["queued"]
            totals["dropped"] += stats["dropped"]
        return totals

    def resetPublishStats(self, cameraIndex: Optional[CameraID] = None) -> None:
        if cameraIndex is not None:
            lane = self._publishLanes.get(cameraIndex)
            if lane is not None:
                lane.resetStats()
            return
        for lane in self._publishLanes.values():
            lane.resetStats()

    def addCamera(
        self,
        cameraIndex: CameraID,
        cameraConfig: CameraConfig,
        path: Union[str, int],
    ) -> bool:
        """
        Adds a camera to the handler using the configured camera backend.

        Args:
            cameraIndex (CameraID): Camera index to add.
            cameraConfig (CameraConfig): Configuration for the camera.
            path (Union[str, int]): Backend-specific camera path/device.

        Returns:
            bool: True if the camera was successfully added, False otherwise.
        """

        try:
            camera = CameraFactory.create(
                cameraType=self.cameraType,
                cameraIndex=cameraIndex,
                path=path,
            )
            handle = CameraHandle(camera, cameraConfig.name, cameraIndex)
            handle.setIndex(cameraIndex)
        except Exception as e:
            log.err(
                f"Failed to start camera capture ({type(e).__name__}): {e}\n"
                f"{traceback.format_exc()}"
            )
            return False

        self.addCameraData(cameraIndex, cameraConfig, handle)

        return True

    def addCameraData(
        self,
        cameraIndex: CameraID,
        cameraConfig: CameraConfig,
        handle: CameraHandle,
    ):
        self.cameraHandles[cameraIndex] = handle

        handle.setIndex(cameraIndex)

        self.streamOutputs[cameraIndex] = self.createStreamOutput(cameraIndex)

        frame = generateNoSignalFrame(handle.name, handle.cameraIndex)

        if frame is not None:
            self.streamOutputs[cameraIndex].putFrame(
                frame
            )  # NOTE: stream only appears after a frame has been posted, probably

        # The streams array is published asynchronously by CSCore. Watch the
        # topic instead of reading it here so camera creation/hotplug never
        # blocks on NetworkTables data that may not exist yet.
        self._registerStreamListener(cameraIndex)

        self.setRecordingStatus(cameraIndex, False)

        self._startPublishLane(cameraIndex)

        self.onAddCamera.call(cameraIndex, cameraConfig.name, handle)

        log.info(
            f"Camera (name={cameraConfig.name}, id={cameraConfig.id}, id={cameraIndex}) added successfully."
        )

    def setCameraProps(
        self, settings: Dict[str, Any], handle: CameraHandle
    ) -> Dict[str, Any]:
        """
        Applies the specified settings to a camera and sets its video mode.

        Args:
            settings (Dict[str, Any]): Dictionary of property names and values to apply.
            camera (CameraHandle): The camera to configure.

            Returns:
            Dict[str, Any]: Dictionary of updated settings (currently unused).
        """
        updated_settings = {}
        for settingName in settings.keys():
            setting_value = settings.get(settingName)
            if setting_value is not None:
                handle.setProperty(
                    prop=settingName,
                    value=setting_value,
                )

        return updated_settings

    def cleanup(self) -> None:
        """Stop the camera scanner and release cameras, streams, and recordings."""
        log.info("Stopping camera scanner...")
        self.stopCameraScanEvent.set()
        # Wake the scanner immediately so cleanup does not wait for a probe interval.
        self._cameraScanRequested.set()
        for cameraIndex in list(self._streamListeners):
            self._unregisterStreamListener(cameraIndex)
        if joinThread(
            getattr(self, "cameraScanningThread", None),
            "Camera scanner",
            timeout=2.0,
        ):
            log.info("Camera scanner stopped.")

        for cameraIndex, lane in list(self._publishLanes.items()):
            lane.stop()
        self._publishLanes.clear()

        recordingCount = len(self.recordingOutputs)
        if recordingCount:
            log.info(f"Releasing {recordingCount} recording(s)...")
        for cameraIndex, record in self.recordingOutputs.items():
            try:
                record.release()
            except Exception as error:
                log.err(
                    f"Failed to release recording for camera #{cameraIndex}: {error}"
                )
        self.recordingOutputs.clear()
        self.recordingResolutions.clear()
        self.recordingStatus.clear()
        self.recordFileNames.clear()
        if recordingCount:
            log.info("Recordings released.")

        cameraCount = len(self.cameraHandles)
        if cameraCount:
            log.info(f"Closing {cameraCount} camera(s)...")
        for cameraIndex, handle in self.cameraHandles.items():
            name = getattr(handle, "name", str(cameraIndex))
            try:
                # Stop the frame grabber before releasing the camera connection.
                handle.close()
                handle.camera.close()
            except Exception as error:
                log.err(f"Failed to close camera #{cameraIndex} ({name}): {error}")
        self.cameraHandles.clear()
        if cameraCount:
            log.info("Cameras closed.")

        streamCount = len(self.streamOutputs)
        if streamCount:
            log.info(f"Clearing {streamCount} stream output(s)...")
        self.streamOutputs.clear()
        self.streamSizes.clear()
        self._streamFrameBuffers.clear()
        self._recordFrameBuffers.clear()
        log.info("Camera resources released.")
