# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import queue
import threading
import time
from typing import Any, cast

import numpy as np
from synapse.core.camera.camera_handle import CameraHandle


def makeHandle() -> CameraHandle:
    handle = object.__new__(CameraHandle)
    handle._frameQueue = queue.Queue(maxsize=1)
    handle._frameReady = threading.Event()
    handle._bufferReturned = threading.Event()
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


def test_connection_checks_are_throttled() -> None:
    handle = makeHandle()
    handle._bufferPool = [
        np.zeros((2, 2, 3), dtype=np.uint8),
        np.zeros((2, 2, 3), dtype=np.uint8),
    ]
    handle._freeBuffers = queue.Queue(maxsize=2)
    handle._freeBuffers.put_nowait(0)
    handle._freeBuffers.put_nowait(1)
    fakeCamera = _FakeCamera()
    handle.camera = cast(Any, fakeCamera)
    handle.cameraIndex = 98
    handle._running = True
    handle._thread = threading.Thread(
        target=handle._frameGrabberLoop, daemon=True, name="test-throttled-checks"
    )

    stopConsumer = threading.Event()

    def consume() -> None:
        while not stopConsumer.is_set():
            ok, _, _ = handle.grabFrame(timeout=0.01)
            if ok:
                handle.releaseFrame()

    consumer = threading.Thread(target=consume, daemon=True, name="test-consumer")
    handle._thread.start()
    consumer.start()

    try:
        assert fakeCamera.progress.wait(1.0)
        time.sleep(0.2)
        assert fakeCamera.count > 20
        assert fakeCamera.connectionChecks <= max(3, fakeCamera.count // 5)
    finally:
        stopConsumer.set()
        handle.close()
        consumer.join(timeout=1.0)


class _FakeCamera:
    def __init__(self) -> None:
        self.count = 0
        self.connectionChecks = 0
        self.progress = threading.Event()

    def isConnected(self) -> bool:
        self.connectionChecks += 1
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
    fakeCamera = _FakeCamera()
    handle.camera = cast(Any, fakeCamera)
    handle.cameraIndex = 99
    handle._running = True
    handle._thread = threading.Thread(
        target=handle._frameGrabberLoop, daemon=True, name="test-frame-grabber"
    )
    handle._thread.start()

    try:
        assert fakeCamera.progress.wait(1.0)
        ok, frame, _ = handle.grabFrame(timeout=1.0)
        assert ok is True
        assert frame is not None

        leasedValue = int(frame[0, 0, 0])
        time.sleep(0.02)
        assert int(frame[0, 0, 0]) == leasedValue
        assert handle.getCaptureStats()["dropped"] >= 1
        with handle._frameMutex:
            assert all(
                isinstance(index, int) and 0 <= index < len(handle._bufferPool)
                for index in handle._freeBuffers.queue
            )

        handle.releaseFrame()
        startCount = fakeCamera.count
        while fakeCamera.count < startCount + 10:
            time.sleep(0.001)

        ok2, nextFrame, _ = handle.grabFrame(timeout=1.0)
        assert ok2 is True
        assert nextFrame is not None
        assert int(nextFrame[0, 0, 0]) != leasedValue
    finally:
        handle.close()
