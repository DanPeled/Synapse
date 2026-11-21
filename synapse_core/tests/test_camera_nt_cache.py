# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock, patch

from synapse.core.camera.camera_handle import CameraHandle
from synapse.core.camera_factory import CameraConfig, getCameraTable
from synapse.core.camera_handler import CameraHandler
from synapse.core.runtime_handler import RuntimeManager


def makeHandle(name: str = "cam0", index: int = 0) -> CameraHandle:
    """Build a handle without starting its frame-grabber thread."""
    handle = object.__new__(CameraHandle)
    handle.name = name
    handle.stream = ""
    handle.cameraIndex = index
    handle.ntTable = None
    handle.ntTableName = ""
    return handle


def makeConfig(name: str = "cam0") -> CameraConfig:
    return CameraConfig(
        name=name,
        id="camera-uid",
        defaultPipeline=0,
        calibration={},
        streamRes=(320, 240),
    )


def test_get_camera_table_follows_rename():
    handler = CameraHandler()
    handle = makeHandle("old")
    handler.cameraHandles[0] = handle
    handler.cameraConfigBindings[0] = makeConfig("old")

    tables = {}

    def getSubTable(name):
        return tables.setdefault(name, MagicMock(name=f"table-{name}"))

    root = MagicMock()
    root.getTable.return_value.getSubTable.side_effect = getSubTable

    with (
        patch(
            "synapse.core.camera_factory.NetworkTableInstance.getDefault",
            return_value=root,
        ),
        patch.object(handler, "_unregisterStreamListener"),
        patch.object(handler, "_registerStreamListener"),
        patch.object(handler, "createStreamOutput", return_value=MagicMock()),
        patch("synapse.core.camera_handler.cs.CameraServer.removeCamera"),
        patch("synapse.core.camera_handler.generateNoSignalFrame", return_value=None),
    ):
        oldTable = getCameraTable(handle)
        handler.renameCamera(0, "new")
        newTable = getCameraTable(handle)

    assert oldTable is tables["old"]
    assert newTable is tables["new"]
    assert handle.name == "new"


def test_add_camera_data_watches_streams_topic():
    handler = CameraHandler()
    handle = makeHandle()
    added = []
    handler.onCameraStreamChanged.add(lambda index, h: added.append((index, h)))

    ntInstance = MagicMock()
    with (
        patch.object(handler, "createStreamOutput", return_value=MagicMock()),
        patch("synapse.core.camera_handler.generateNoSignalFrame", return_value=None),
        patch(
            "synapse.core.camera_handler.NetworkTableInstance.getDefault",
            return_value=ntInstance,
        ),
    ):
        handler.addCameraData(0, makeConfig(), handle)

    # Camera creation must not read the streams array synchronously.
    entry = ntInstance.getTable.return_value.getSubTable.return_value.getSubTable.return_value.getEntry.return_value
    entry.getStringArray.assert_not_called()

    addListenerArgs = ntInstance.addListener.call_args.args
    assert addListenerArgs[0] is entry
    callback = addListenerArgs[2]

    event = SimpleNamespace(
        data=SimpleNamespace(
            value=SimpleNamespace(
                getStringArray=lambda: [
                    "mjpg:http://first:1181/stream.mjpg",
                    "mjpg:http://camera:1181/stream.mjpg",
                ]
            )
        )
    )
    callback(event)

    # The historical [1] entry is preferred and the mjpg: prefix is stripped.
    assert handle.stream == "http://camera:1181/stream.mjpg"
    assert added == [(0, handle)]

    # Repeated or malformed NT data never breaks setup or emits duplicate adds.
    for streams in (
        [],
        [""],
        ["not-a-url"],
        None,
        "mjpg:http://camera:1181/stream.mjpg",
        [1, None, "mjpg:http://camera:1181/stream.mjpg"],
    ):
        event = SimpleNamespace(
            data=SimpleNamespace(
                value=SimpleNamespace(getStringArray=lambda s=streams: s)
            )
        )
        callback(event)

    assert handle.stream == "http://camera:1181/stream.mjpg"
    assert added == [(0, handle)]


def test_rename_moves_stream_listener_to_new_topic():
    handler = CameraHandler()
    handle = makeHandle("old")
    handler.cameraHandles[0] = handle
    handler.cameraConfigBindings[0] = makeConfig("old")

    ntInstance = MagicMock()
    ntInstance.addListener.return_value = 99
    subTable = ntInstance.getTable.return_value.getSubTable.return_value
    with (
        patch(
            "synapse.core.camera_handler.NetworkTableInstance.getDefault",
            return_value=ntInstance,
        ),
        patch("synapse.core.camera_handler.cs.CameraServer.removeCamera"),
        patch.object(handler, "createStreamOutput", return_value=MagicMock()),
        patch("synapse.core.camera_handler.generateNoSignalFrame", return_value=None),
    ):
        handler._registerStreamListener(0)
        assert subTable.getSubTable.call_args.args == ("old",)

        handler.renameCamera(0, "new")

    ntInstance.removeListener.assert_called_once_with(99)
    assert subTable.getSubTable.call_args.args == ("new",)
    assert handle.stream == ""


def test_runtime_rebind_replaces_only_renamed_camera_nt_state():
    manager = object.__new__(RuntimeManager)
    manager.isSetup = True
    handle = makeHandle("new")
    manager.cameraHandler = MagicMock()
    manager.cameraHandler.getCameraHandle.return_value = handle
    manager.pipelineBindings = {0: 2}

    publisher0 = MagicMock()
    publisher1 = MagicMock()
    latencyPublisher = MagicMock()
    manager.propPubs = {(0, "brightness"): publisher0, (1, "brightness"): publisher1}
    manager._latencyPubs = {(0, "captureLatency"): latencyPublisher}
    manager.cameraFrameEntries = cast(Any, {0: "entry0", 1: "entry1"})
    manager.cameraViewIDs = {0: "default", 1: "other"}
    setattr(manager, "_RuntimeManager__pipelineEntryCache", {0: "entry0", 1: "entry1"})
    manager._ntListenerKeys = {(0, "pipeline", ""): 10, (1, "pipeline", ""): 11}
    manager._ntListeners = [10, 11]

    with (
        patch("synapse.core.runtime_handler.NetworkTableInstance.getDefault") as nt,
        patch.object(manager, "_setupCameraRecordListener") as setupRecord,
        patch.object(manager, "_setupCameraPipelineListener") as setupPipeline,
        patch.object(manager, "setPipelineByIndex") as setPipeline,
    ):
        manager._rebindCameraNt(0)

    nt.return_value.removeListener.assert_called_once_with(10)
    assert manager._ntListeners == [11]
    publisher0.close.assert_called_once()
    latencyPublisher.close.assert_called_once()
    publisher1.close.assert_not_called()
    assert 0 not in manager.propPubs
    assert 0 not in manager._latencyPubs
    assert 0 not in manager.cameraFrameEntries
    assert 0 not in manager.cameraViewIDs
    assert 0 not in getattr(manager, "_RuntimeManager__pipelineEntryCache")
    assert (1, "brightness") in manager.propPubs
    setupRecord.assert_called_once_with(0, handle)
    setupPipeline.assert_called_once_with(0, handle)
    setPipeline.assert_called_once_with(0, 2)
