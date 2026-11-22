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
    handle._freeBuffers = queue.Queue(maxsize=1)
    handle._freeBuffers.put_nowait(0)
    handle._leasedIndex = None
    handle._bufferGeneration = 0
    handle._capturedFrames = 0
    handle._droppedFrames = 0
    handle._staleFrames = 0
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


class _FakeCamera:
    def __init__(self) -> None:
        self.count = 0
        self.progress = threading.Event()

    def isConnected(self) -> bool:
        return True

    def grabFrame(self, buffer):
        self.count += 1
        buffer[0, 0, 0] = self.count % 251 + 1
        if self.count >= 2:
            self.progress.set()
        time.sleep(0.001)
        return int(time.monotonic() * 1_000_000), buffer


def test_leased_buffer_is_not_overwritten_by_capture_thread() -> None:
    handle = makeHandle()
    handle._bufferPool = [
        np.zeros((2, 2, 3), dtype=np.uint8),
        np.zeros((2, 2, 3), dtype=np.uint8),
    ]
    handle._freeBuffers = queue.Queue(maxsize=2)
    handle._freeBuffers.put_nowait(0)
    handle._freeBuffers.put_nowait(1)
    handle.camera = _FakeCamera()
    handle.cameraIndex = 99
    handle._running = True
    handle._thread = threading.Thread(
        target=handle._frameGrabberLoop, daemon=True, name="test-frame-grabber"
    )
    handle._thread.start()

    try:
        assert handle.camera.progress.wait(1.0)
        ok, frame, _ = handle.grabFrame(timeout=1.0)
        assert ok is True
        assert frame is not None

        leasedValue = int(frame[0, 0, 0])
        time.sleep(0.02)
        assert int(frame[0, 0, 0]) == leasedValue
        assert handle.getCaptureStats()["dropped"] >= 1

        handle.releaseFrame()
        startCount = handle.camera.count
        while handle.camera.count < startCount + 10:
            time.sleep(0.001)

        ok2, nextFrame, _ = handle.grabFrame(timeout=1.0)
        assert ok2 is True
        assert nextFrame is not None
        assert int(nextFrame[0, 0, 0]) != leasedValue
    finally:
        handle.close()
