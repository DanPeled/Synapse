# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import threading
import time
from collections import deque
from typing import Any, cast

import numpy as np
from synapse.core.camera.camera_handle import CameraHandle


def makeHandle() -> CameraHandle:
    handle = object.__new__(CameraHandle)
    handle._frameMutex = threading.Lock()
    handle._frameCondition = threading.Condition(handle._frameMutex)
    handle._bufferCondition = threading.Condition(handle._frameMutex)
    handle._frameQueue = deque(maxlen=1)
    handle._bufferPool = [np.zeros((2, 2, 3), dtype=np.uint8)]
    handle._freeBuffers = deque([(0, 0)])
    handle._leasedIndex = None
    handle._leasedGeneration = None
    handle._bufferGeneration = 0
    handle._capturedFrames = 0
    handle._droppedFrames = 0
    handle._staleFrames = 0
    handle._running = True
    handle._thread = None
    return handle


def publishFrame(handle: CameraHandle, capturedAt: int) -> None:
    with handle._frameMutex:
        handle._frameQueue.append((capturedAt, handle._bufferGeneration, 0))
        handle._frameCondition.notify()


def test_stale_generation_return_is_discarded() -> None:
    handle = makeHandle()
    with handle._frameMutex:
        handle._bufferGeneration = 1
        handle._freeBuffers.clear()

        handle._returnBufferLocked(0, 0)
        assert len(handle._freeBuffers) == 0

        handle._returnBufferLocked(1, 0)
        assert list(handle._freeBuffers) == [(1, 0)]


def test_grab_frame_returns_capture_latency() -> None:
    handle = makeHandle()
    capturedAt = int((time.monotonic() - 0.05) * 1_000_000)
    publishFrame(handle, capturedAt)

    ok, frame, captureLatency = handle.grabFrame(timeout=0.1)

    assert ok is True
    assert frame is handle._bufferPool[0]
    assert 0.04 < captureLatency < 0.1
    assert len(handle._frameQueue) == 0


def test_grab_frame_wakes_on_frame_condition() -> None:
    handle = makeHandle()

    def publishFrameFromThread() -> None:
        time.sleep(0.05)
        publishFrame(handle, int(time.monotonic() * 1_000_000))

    publisher = threading.Thread(target=publishFrameFromThread)
    publisher.start()
    started = time.monotonic()
    ok, _, _ = handle.grabFrame(timeout=1)
    elapsed = time.monotonic() - started
    publisher.join()

    assert ok is True
    assert elapsed < 0.25


def test_taken_lease_is_not_released_by_the_next_grab() -> None:
    handle = makeHandle()
    handle._bufferPool.append(np.zeros((2, 2, 3), dtype=np.uint8))
    publishFrame(handle, int(time.monotonic() * 1_000_000))

    ok, frame, _ = handle.grabFrame(timeout=0.1)
    assert ok is True
    assert frame is handle._bufferPool[0]

    lease = handle.takeLease()
    assert lease == (0, 0)
    assert handle._leasedIndex is None

    with handle._frameMutex:
        # ``publishFrame`` bypasses the free list; clear its initial entry so
        # the assertion below only observes releases performed by grabFrame.
        handle._freeBuffers.clear()
        handle._freeBuffers.append((0, 1))
        handle._frameQueue.append((int(time.monotonic() * 1_000_000), 0, 1))
        handle._frameCondition.notify()

    ok, nextFrame, _ = handle.grabFrame(timeout=0.1)
    assert ok is True
    assert nextFrame is handle._bufferPool[1]
    with handle._frameMutex:
        assert (0, 0) not in handle._freeBuffers

    handle.returnLease(cast(Any, lease))
    with handle._frameMutex:
        assert (0, 0) in handle._freeBuffers


def test_connection_checks_are_throttled() -> None:
    handle = makeHandle()
    handle._bufferPool = [
        np.zeros((2, 2, 3), dtype=np.uint8),
        np.zeros((2, 2, 3), dtype=np.uint8),
    ]
    handle._freeBuffers = deque([(0, 0), (0, 1)])
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
    handle._freeBuffers = deque([(0, 0), (0, 1)])
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
        # The grabber drains a stalled sink on a 20 ms ceiling, so allow more
        # than one drain window before asserting the counter moved.
        time.sleep(0.05)
        assert int(frame[0, 0, 0]) == leasedValue
        assert handle.getCaptureStats()["dropped"] >= 1
        with handle._frameMutex:
            assert all(
                generation == handle._bufferGeneration
                and isinstance(index, int)
                and 0 <= index < len(handle._bufferPool)
                for generation, index in handle._freeBuffers
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
