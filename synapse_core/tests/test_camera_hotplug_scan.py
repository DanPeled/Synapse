# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import threading
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

from synapse.core.camera_handler import CameraHandler


def _usbInfo(name: str, productId: int, dev: int):
    return SimpleNamespace(
        name=name,
        productId=productId,
        dev=dev,
        path=f"/dev/video{dev}",
        otherPaths=[],
        vendorId=1,
    )


def test_create_cameras_enumerates_once_and_reuses_map() -> None:
    handler = CameraHandler()
    infos = [_usbInfo("cam", 10, 0)]

    with (
        patch(
            "synapse.core.camera_handler.GlobalSettings.getCameraConfigMap",
            return_value={},
        ),
        patch(
            "synapse.core.camera_handler.cs.UsbCamera.enumerateUsbCameras",
            return_value=infos,
        ) as enumerateCameras,
        patch("synapse.core.camera_handler.GlobalSettings.setCameraConfig"),
        patch.object(handler, "addCamera", return_value=True) as addCamera,
        patch.object(handler, "scanCameras", wraps=handler.scanCameras) as scanCameras,
    ):
        handler.createCameras()

    assert enumerateCameras.call_count == 1
    scanCameras.assert_called_once()
    assert scanCameras.call_args.kwargs["usbCameraInfos"] == handler.usbCameraInfos
    assert list(handler.usbCameraInfos) == ["cam_10"]
    addCamera.assert_called_once()


def test_explicit_request_wakes_scanner_without_long_wait() -> None:
    handler = CameraHandler()
    scanned = threading.Event()

    with (
        patch("synapse.core.camera_handler.os.makedirs"),
        patch.object(handler, "createCameras"),
        patch(
            "synapse.core.camera_handler._getUsbDeviceSignature",
            return_value=(("video0", 1, 1),),
        ),
        patch.object(
            handler, "scanCameras", side_effect=lambda **_: scanned.set()
        ) as scanCameras,
    ):
        try:
            handler.setup()
            handler.requestCameraScan()
            assert scanned.wait(1.0)
        finally:
            handler.cleanup()

    scanCameras.assert_called_once()
    assert handler._cameraProbeInterval < 10.0


def test_device_signature_change_triggers_scan_without_enumeration() -> None:
    handler = CameraHandler()
    stable = (("video0", 1, 1),)
    plugged = stable + (("video1", 2, 2),)

    with (
        patch(
            "synapse.core.camera_handler._getUsbDeviceSignature",
            side_effect=[stable, stable, plugged],
        ),
        patch(
            "synapse.core.camera_handler.cs.UsbCamera.enumerateUsbCameras",
            side_effect=AssertionError("no enumeration needed for direct detection"),
        ),
    ):
        assert handler._checkForCameraChanges() is False
        assert handler._checkForCameraChanges() is False
        assert handler._checkForCameraChanges() is True

    assert handler._cameraProbeInterval == handler.cameraChangePollInterval
    assert handler._cameraProbeInterval < 10.0

    with patch(
        "synapse.core.camera_handler._getUsbDeviceSignature",
        return_value=plugged,
    ):
        assert handler._checkForCameraChanges() is False


def test_stable_fallback_backs_off_without_full_rescans() -> None:
    handler = CameraHandler()
    infos = [_usbInfo("cam", 10, 0)]

    with (
        patch("synapse.core.camera_handler._getUsbDeviceSignature", return_value=None),
        patch(
            "synapse.core.camera_handler.cs.UsbCamera.enumerateUsbCameras",
            return_value=infos,
        ) as enumerateCameras,
        patch("synapse.core.camera_handler.GlobalSettings.setCameraConfig"),
        patch.object(handler, "addCamera", return_value=True),
        patch.object(handler, "scanCameras", wraps=handler.scanCameras) as scanCameras,
    ):
        handler.scanCameras(usbCameraInfos=handler._enumerateUsbCameras())
        enumerateCameras.reset_mock()
        scanCameras.reset_mock()

        delays = []
        for _ in range(5):
            assert handler._checkForCameraChanges() is False
            delays.append(handler._cameraProbeInterval)

        assert delays == [2.0, 4.0, 8.0, 16.0, 30.0]
        assert enumerateCameras.call_count == 5
        scanCameras.assert_not_called()

        enumerateCameras.return_value = infos + [_usbInfo("cam2", 20, 1)]
        assert handler._checkForCameraChanges() is True
        assert handler._pendingUsbCameraInfos is not None
        assert handler._cameraProbeInterval == handler.cameraScanMinInterval

        enumerationCount = enumerateCameras.call_count
        handler.scanCameras(usbCameraInfos=handler._pendingUsbCameraInfos)
        assert enumerateCameras.call_count == enumerationCount
        scanCameras.assert_called_once()


def test_explicit_request_forces_fresh_scan() -> None:
    handler = CameraHandler()
    handler._pendingUsbCameraInfos = cast(Any, {"stale": _usbInfo("stale", 1, 0)})

    handler.requestCameraScan()

    assert handler._checkForCameraChanges() is True
    assert handler._pendingUsbCameraInfos is None
    assert not handler._cameraScanRequested.is_set()
