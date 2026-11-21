# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import queue
import threading
import time

import numpy as np

from synapse.core.camera.camera_handle import CameraHandle


def makeHandle() -> CameraHandle:
    handle = object.__new__(CameraHandle)
    handle._frameQueue = queue.Queue(maxsize=1)
    handle._frameReady = threading.Event()
    handle._frameMutex = threading.Lock()
    handle._bufferPool = [np.zeros((2, 2, 3), dtype=np.uint8)]
    return handle


def test_grab_frame_returns_capture_latency() -> None:
    handle = makeHandle()
    capturedAt = int((time.monotonic() - 0.05) * 1_000_000)

    with handle._frameMutex:
        handle._frameQueue.put_nowait((capturedAt, 0))
        handle._frameReady.set()

    ok, frame, captureLatency = handle.grabFrame(timeout=0.1)

    assert ok is True
    assert frame is handle._bufferPool[0]
    assert 0.04 < captureLatency < 0.1
    assert handle._frameReady.is_set() is False


def test_grab_frame_wakes_on_frame_event() -> None:
    handle = makeHandle()

    def publishFrame() -> None:
        time.sleep(0.05)
        capturedAt = int(time.monotonic() * 1_000_000)
        with handle._frameMutex:
            handle._frameQueue.put_nowait((capturedAt, 0))
            handle._frameReady.set()

    publisher = threading.Thread(target=publishFrame)
    publisher.start()
    started = time.monotonic()
    ok, _, _ = handle.grabFrame(timeout=1)
    elapsed = time.monotonic() - started
    publisher.join()

    assert ok is True
    assert elapsed < 0.25
