# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Simulated camera that renders the field instead of reading a real device.

``SimCamera`` implements the same interface as a physical camera, so the runtime
and pipelines do not need to know where the frames come from. The robot and
camera poses are read from NetworkTables, and the rendered frames flow through
the normal ``CameraHandle``/cscore/UI path.
"""

import threading
import time
from typing import List, Optional, Set, Tuple, Union

import cv2
import numpy as np
from cscore import VideoMode
from ntcore import NetworkTable, NetworkTableInstance
from synapse.core.camera.synapse_camera import SynapseCamera
from synapse.log import warn
from synapse.stypes import CameraID, Frame, PropertyMetaDict, Size
from synapse_net.nt_client import NtClient
from wpimath.geometry import Pose3d, Rotation3d, Transform3d, Translation3d

from .model import (DEFAULT_CAMERA_OFFSET, DEFAULT_ROBOT_POSE, MAX_FPS,
                    SUPPORTED_RESOLUTIONS)
from .three import camera_spec
from .viewer import STARTUP_TIMEOUT, getViewer

PoseValues = List[float]


class SimCamera(SynapseCamera):
    """Camera implementation that renders a simulated view of the field."""

    #: Subtable of the Synapse NetworkTables table containing simulation state.
    TABLE_NAME = "sim"
    #: ``[x, y, yaw]`` in metres and radians.
    ROBOT_POSE_KEY = "robot_pose"
    #: ``[x, y, z, roll, pitch, yaw]`` relative to the robot, in metres/radians.
    CAMERA_OFFSET_KEY = "camera_offset"
    #: Optional absolute ``[x, y, z, roll, pitch, yaw]`` camera pose.
    CAMERA_POSE_KEY = "camera_pose"
    #: Per-camera overrides live under cameras/<index>
    CAMERAS_TABLE = "cameras"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._running = True
        self._index: CameraID = -1
        self._mode = VideoMode(
            VideoMode.PixelFormat.kMJPEG,
            SUPPORTED_RESOLUTIONS[0][0],
            SUPPORTED_RESOLUTIONS[0][1],
            int(MAX_FPS),
        )
        self._lastFrameTime = 0.0
        self._lastFrameSeq = -1

        self._viewer = getViewer()
        self._viewerStarted = False

        self._table: Optional[NetworkTable] = None
        self._cameraSubTable: Optional[NetworkTable] = None
        self._warnedKeys: Set[Tuple[str, str]] = set()

    @classmethod
    def create(cls, *_, path: Union[str, int], index: CameraID) -> "SimCamera":
        inst = SimCamera()
        inst._index = index
        return inst

    # ------------------------------------------------------------------
    # NetworkTables state
    # ------------------------------------------------------------------

    def _networkTable(self) -> NetworkTable:
        if self._table is None:
            self._table = (
                NetworkTableInstance.getDefault()
                .getTable(NtClient.NT_TABLE)
                .getSubTable(self.TABLE_NAME)
            )
        return self._table

    def _cameraNetworkTable(self) -> Optional[NetworkTable]:
        """Returns the per-camera override table, or ``None`` without an index."""
        if self._index < 0:
            return None
        if self._cameraSubTable is None:
            self._cameraSubTable = (
                self._networkTable()
                .getSubTable(self.CAMERAS_TABLE)
                .getSubTable(str(self._index))
            )
        return self._cameraSubTable

    @staticmethod
    def _poseValues(
        table: NetworkTable, key: str, default: Optional[PoseValues]
    ) -> Optional[PoseValues]:
        values = list(table.getEntry(key).getDoubleArray(default or []))
        if not values:
            return default
        return values

    def _poseValue(
        self, key: str, default: Optional[PoseValues]
    ) -> Optional[PoseValues]:
        """Reads a per-camera override, falling back to the global simulation key."""
        cameraTable = self._cameraNetworkTable()
        if cameraTable is not None:
            values = self._poseValues(cameraTable, key, None)
            if values is not None:
                return values
        return self._poseValues(self._networkTable(), key, default)

    def _warnOnce(self, key: str, message: str) -> None:
        """Logs an invalid override once instead of on every rendered frame."""
        warningKey = (str(self._index), key)
        if warningKey in self._warnedKeys:
            return
        self._warnedKeys.add(warningKey)
        warn(message)

    @staticmethod
    def _translation(values: PoseValues) -> Translation3d:
        return Translation3d(values[0], values[1], values[2])

    @staticmethod
    def _rotation(values: PoseValues) -> Rotation3d:
        return Rotation3d(values[3], values[4], values[5])

    def poses(self) -> Tuple[Pose3d, Pose3d]:
        """Returns ``(robotPose, cameraPose)`` from NetworkTables.

        Per-camera overrides under ``sim/cameras/<index>`` take precedence over
        the shared ``sim`` defaults, so several simulated cameras can be placed
        independently while single-camera setups only need one set of keys.
        """
        robotValues = self._poseValue(self.ROBOT_POSE_KEY, DEFAULT_ROBOT_POSE)
        assert robotValues is not None
        if len(robotValues) < 3:
            self._warnOnce(
                self.ROBOT_POSE_KEY,
                f"Simulation {self.ROBOT_POSE_KEY} must be [x, y, yaw]; "
                "using the default robot pose",
            )
            robotValues = DEFAULT_ROBOT_POSE
        robotPose = Pose3d(
            Translation3d(robotValues[0], robotValues[1], 0.0),
            Rotation3d(0.0, 0.0, robotValues[2]),
        )

        cameraValues = self._poseValue(self.CAMERA_POSE_KEY, None)
        if cameraValues is not None and len(cameraValues) >= 6:
            cameraPose = Pose3d(
                self._translation(cameraValues), self._rotation(cameraValues)
            )
        else:
            if cameraValues is not None:
                self._warnOnce(
                    self.CAMERA_POSE_KEY,
                    f"Simulation {self.CAMERA_POSE_KEY} must be "
                    "[x, y, z, roll, pitch, yaw]; using the robot-relative offset",
                )

            offsetValues = self._poseValue(
                self.CAMERA_OFFSET_KEY, DEFAULT_CAMERA_OFFSET
            )
            assert offsetValues is not None
            if len(offsetValues) < 6:
                self._warnOnce(
                    self.CAMERA_OFFSET_KEY,
                    f"Simulation {self.CAMERA_OFFSET_KEY} must be "
                    "[x, y, z, roll, pitch, yaw]; using the default offset",
                )
                offsetValues = DEFAULT_CAMERA_OFFSET

            cameraPose = robotPose.transformBy(
                Transform3d(
                    self._translation(offsetValues),
                    self._rotation(offsetValues),
                )
            )

        return robotPose, cameraPose

    # ------------------------------------------------------------------
    # Frame production
    # ------------------------------------------------------------------

    def grabFrame(self, buffer: np.ndarray) -> Tuple[float, Optional[Frame]]:
        if not self._running:
            return 0.0, None

        with self._lock:
            width = int(self._mode.width)
            height = int(self._mode.height)
            fps = float(self._mode.fps) if self._mode.fps > 0 else MAX_FPS

        self._throttle(fps)

        try:
            if not self._viewerStarted:
                self._viewer.ensureStarted(STARTUP_TIMEOUT)
                self._viewerStarted = True

            _, cameraPose = self.poses()
            spec = camera_spec(self._index, width, height, cameraPose)
            self._viewer.setSpec(self._index, spec)

            # Consume the newest frame the renderer has finished. The renderer
            # runs independently of this thread, so a frame may correspond to
            # a slightly older spec; that is the same as a real camera exposing
            # one frame of latency and avoids serialising render and transfer.
            seq, payload = self._viewer.takeFrame(self._index, self._lastFrameSeq)
            self._lastFrameSeq = seq

            frame = self._decodeFrame(payload, width, height)
        except Exception as error:
            warn(f"Simulation camera failed to render a frame: {error}")
            return 0.0, None

        if buffer is not None:
            bufferHeight, bufferWidth = buffer.shape[:2]
            if frame.shape[0] != bufferHeight or frame.shape[1] != bufferWidth:
                resized = cv2.resize(
                    frame,
                    (bufferWidth, bufferHeight),
                    interpolation=cv2.INTER_AREA,
                )
                buffer[:] = resized
            else:
                buffer[:] = frame
            return time.time(), buffer

        return time.time(), frame

    @staticmethod
    def _decodeFrame(payload: bytes, width: int, height: int) -> np.ndarray:
        """Converts the renderer's bottom-up RGBA pixels to a BGR image."""
        pixels = np.frombuffer(payload, dtype=np.uint8)
        if pixels.size == width * height * 4:
            rgba = pixels.reshape((height, width, 4))
            # OpenGL reads rows bottom-up; flip once so the image matches the
            # coordinate system used by real cameras and by calibration.
            frame = cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGR)
            cv2.flip(frame, 0, dst=frame)
            return frame

        # Older renderers uploaded JPEG; accept it for forward compatibility.
        frame = cv2.imdecode(pixels, cv2.IMREAD_COLOR)
        if frame is None:
            raise RuntimeError("Failed to decode simulated camera frame")
        return frame

    def _throttle(self, fps: float) -> None:
        period = 1.0 / max(1.0, fps)
        now = time.monotonic()
        wait = self._lastFrameTime + period - now
        if wait > 0.0:
            time.sleep(wait)
            now = time.monotonic()
        self._lastFrameTime = now

    def close(self) -> None:
        self._running = False
        self._viewer.removeSpec(self._index)

    def isConnected(self) -> bool:
        return self._running

    # ------------------------------------------------------------------
    # Camera properties / modes
    # ------------------------------------------------------------------

    def setProperty(self, prop: str, value: Union[int, float]) -> None:
        # Simulated frames have no hardware properties.
        pass

    def getProperty(self, prop: str) -> Union[int, float, None]:
        return None

    def getPropertyMeta(self) -> PropertyMetaDict:
        return {}

    def setVideoMode(self, videoMode: VideoMode) -> None:
        with self._lock:
            self._mode = VideoMode(
                VideoMode.PixelFormat.kMJPEG,
                max(1, int(videoMode.width)),
                max(1, int(videoMode.height)),
                max(1, int(videoMode.fps)) if videoMode.fps > 0 else int(MAX_FPS),
            )

    def getResolution(self) -> Size:
        with self._lock:
            return int(self._mode.width), int(self._mode.height)

    def getSupportedResolutions(self) -> List[Size]:
        return [(width, height) for width, height in SUPPORTED_RESOLUTIONS]

    def getMaxFPS(self) -> float:
        return MAX_FPS

    def enumerateVideoModes(self) -> List[VideoMode]:
        return [
            VideoMode(VideoMode.PixelFormat.kMJPEG, width, height, int(MAX_FPS))
            for width, height in SUPPORTED_RESOLUTIONS
        ]

    def getVideoMode(self) -> VideoMode:
        with self._lock:
            return VideoMode(
                VideoMode.PixelFormat.kMJPEG,
                self._mode.width,
                self._mode.height,
                self._mode.fps,
            )
