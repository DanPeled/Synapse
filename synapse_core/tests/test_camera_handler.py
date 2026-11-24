# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import threading
import time
import unittest
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
from synapse.core.camera_handler import CameraHandler, _PublishLane


class TestCameraHandler(unittest.TestCase):
    def setUp(self):
        self.handler = CameraHandler()

    def test_getCamera_returns_correct_camera(self):
        mock_camera = MagicMock()
        self.handler.cameraHandles[2] = mock_camera
        self.assertEqual(self.handler.getCameraHandle(2), mock_camera)

    # TODO: add camera tests


class TestPublishFrame(unittest.TestCase):
    def setUp(self):
        self.handler = CameraHandler()
        self.handler.publishInterval = 0.0
        self.handler.streamSizes[0] = (320, 240)

        self.handle = MagicMock()
        self.handle.cameraIndex = 0
        self.handle.name = "cam0"

        self.output = MagicMock()
        self.handler.streamOutputs[0] = self.output

    def test_fps_overlay_is_drawn_only_for_published_frames(self):
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        self.handler.publishInterval = 1.0
        self.handler.lastPublishTime[0] = time.perf_counter()

        with patch("synapse.core.camera_handler.cv2.putText") as putText:
            self.handler.publishFrame(frame, self.handle, fps=30)
            putText.assert_not_called()

            self.handler.lastPublishTime[0] = 0.0
            self.handler.publishFrame(frame, self.handle, fps=30)

        putText.assert_called_once()

    def test_skips_resize_when_frame_matches_stream_size(self):
        frame = np.zeros((240, 320, 3), dtype=np.uint8)

        with patch("synapse.core.camera_handler.cv2.resize") as resize:
            self.handler.publishFrame(frame, self.handle)

        resize.assert_not_called()
        self.output.putFrame.assert_called_once_with(frame)

    def test_fps_overlay_is_drawn_on_the_resized_stream_frame(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        with patch("synapse.core.camera_handler.cv2.putText") as putText:
            self.handler.publishFrame(frame, self.handle, fps=30)

        drawn = putText.call_args.args[0]
        self.assertEqual(drawn.shape, (240, 320, 3))
        self.assertIsNot(drawn, frame)

    def test_publication_can_be_disabled_for_headless_benchmarks(self):
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        self.handler.setPublishingEnabled(False)

        self.handler.publishFrame(frame, self.handle)

        self.output.putFrame.assert_not_called()
        self.assertEqual(self.handler.getPublishStats(), {"queued": 0, "dropped": 0})

    def test_resizes_and_reuses_destination_buffer(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        self.handler.publishFrame(frame, self.handle)
        first = self.output.putFrame.call_args[0][0]

        self.handler.publishFrame(frame, self.handle)
        second = self.output.putFrame.call_args[0][0]

        self.assertEqual(first.shape, (240, 320, 3))
        self.assertIs(first, second)

    def test_stream_resize_uses_linear_interpolation(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        with patch("synapse.core.camera_handler.cv2.resize") as resize:
            self.handler.publishFrame(frame, self.handle)

        resize.assert_called_once()
        self.assertEqual(resize.call_args.kwargs["interpolation"], cv2.INTER_LINEAR)

    def test_recording_resize_keeps_area_interpolation(self):
        self.handler.recordingStatus[0] = True
        self.handler.recordingResolutions[0] = (320, 240)
        self.handler.cameraHandles[0] = MagicMock()
        self.handler.recordingOutputs[0] = MagicMock()
        frame = np.zeros((480, 640, 3), dtype=np.uint8)

        with patch("synapse.core.camera_handler.cv2.resize") as resize:
            self.handler.publishFrame(frame, self.handle)

        self.assertEqual(resize.call_count, 2)
        self.assertEqual(
            [call.kwargs["interpolation"] for call in resize.call_args_list],
            [cv2.INTER_LINEAR, cv2.INTER_AREA],
        )

    def test_publish_lane_replaces_stale_frames_without_blocking(self):
        self.handler.cameraHandles[0] = self.handle
        started = threading.Event()
        release = threading.Event()
        self.output.putFrame.side_effect = lambda *_: (
            started.set(),
            release.wait(1.0),
        )
        lane = self.handler._startPublishLane(0)
        frame = np.zeros((240, 320, 3), dtype=np.uint8)

        try:
            self.handler.publishFrame(frame, self.handle)
            assert started.wait(1.0)

            startedAt = time.perf_counter()
            self.handler.publishFrame(frame.copy(), self.handle)
            self.handler.publishFrame(frame.copy(), self.handle)
            assert time.perf_counter() - startedAt < 0.1

            assert self.handler.getPublishStats(0)["dropped"] >= 1
        finally:
            release.set()
            lane.stop()

    def test_publish_lane_reuses_the_replaced_buffer(self):
        self.handler.cameraHandles[0] = self.handle
        started = threading.Event()
        release = threading.Event()
        self.output.putFrame.side_effect = lambda *_: (
            started.set(),
            release.wait(1.0),
        )
        lane = self.handler._startPublishLane(0)
        frame = np.zeros((240, 320, 3), dtype=np.uint8)

        try:
            self.handler.publishFrame(frame, self.handle)
            assert started.wait(1.0)

            self.handler.publishFrame(frame.copy(), self.handle)
            queued = lane.frames.queue[0][0]
            self.handler.publishFrame(frame.copy(), self.handle)

            assert lane.frames.queue[0][0] is queued
        finally:
            release.set()
            lane.stop()

    def test_publish_lane_wakes_immediately_after_idle(self):
        self.handler.cameraHandles[0] = self.handle
        lane = self.handler._startPublishLane(0)
        frame = np.zeros((240, 320, 3), dtype=np.uint8)

        try:
            # Let the lane settle into its idle wait before publishing.
            time.sleep(0.05)
            startedAt = time.perf_counter()
            self.handler.publishFrame(frame, self.handle)

            deadline = startedAt + 0.2
            while not self.output.putFrame.called and time.perf_counter() < deadline:
                time.sleep(0.005)

            assert self.output.putFrame.called
            assert time.perf_counter() - startedAt < 0.2
        finally:
            lane.stop()

    def test_publish_lane_reports_sink_failures(self):
        def fail(*_):
            raise RuntimeError("sink failed")

        lane = _PublishLane(0, fail)
        lane.start()

        try:
            lane.enqueue(np.zeros((2, 2, 3), dtype=np.uint8), None)
            deadline = time.perf_counter() + 2.0
            while lane.stats()["failed"] == 0 and time.perf_counter() < deadline:
                time.sleep(0.005)

            assert lane.stats()["failed"] == 1
        finally:
            lane.stop()

    def test_publish_lane_releases_a_queued_lease_on_stop(self):
        lane = _PublishLane(0, MagicMock())
        release = MagicMock()
        lane.enqueueBorrowed(np.zeros((2, 2, 3), dtype=np.uint8), None, release)

        lane.stop()

        release.assert_called_once_with()
        assert lane.stats()["queued"] == 0

    def test_publish_frame_transfers_camera_buffer_lease(self):
        self.handler.cameraHandles[0] = self.handle
        lane = MagicMock()
        self.handler._publishLanes[0] = lane
        frame = np.zeros((2, 2, 3), dtype=np.uint8)
        lease = (4, 2)

        transferred = self.handler.publishFrame(frame, self.handle, lease=lease)

        assert transferred is True
        args = lane.enqueueBorrowed.call_args.args
        assert args[0] is frame
        assert args[1] is None

        release = args[2]
        self.handle.returnLease.assert_not_called()
        release()
        self.handle.returnLease.assert_called_once_with(lease)

    def test_publish_throttle_uses_the_camera_maximum_fps(self):
        handle = MagicMock()
        handle.cameraIndex = 5
        handle.camera.getMaxFPS.return_value = 100
        lane = MagicMock()
        self.handler._publishLanes[5] = lane
        frame = np.zeros((2, 2, 3), dtype=np.uint8)

        with patch(
            "synapse.core.camera_handler.time.perf_counter", side_effect=[1.0, 1.015]
        ):
            self.handler.publishFrame(frame, handle)
            self.handler.publishFrame(frame, handle)

        assert lane.enqueue.call_count == 2
        assert self.handler._publishIntervals[5] == 0.0

    def test_publish_tolerance_accepts_slightly_early_frames_when_capped(self):
        handle = MagicMock()
        handle.cameraIndex = 7
        handle.camera.getMaxFPS.return_value = 240
        lane = MagicMock()
        self.handler._publishLanes[7] = lane
        frame = np.zeros((2, 2, 3), dtype=np.uint8)

        with patch(
            "synapse.core.camera_handler.time.perf_counter", side_effect=[1.0, 1.007]
        ):
            self.handler.publishFrame(frame, handle)
            self.handler.publishFrame(frame, handle)

        assert lane.enqueue.call_count == 2

    def test_publish_does_not_throttle_cameras_within_the_cap(self):
        handle = MagicMock()
        handle.cameraIndex = 6
        handle.camera.getMaxFPS.return_value = 30
        lane = MagicMock()
        self.handler._publishLanes[6] = lane
        frame = np.zeros((2, 2, 3), dtype=np.uint8)

        with patch(
            "synapse.core.camera_handler.time.perf_counter", side_effect=[1.0, 1.005]
        ):
            self.handler.publishFrame(frame, handle)
            self.handler.publishFrame(frame, handle)

        assert lane.enqueue.call_count == 2

    def test_recording_resizes_and_releases_buffer(self):
        self.handler.recordingStatus[0] = True
        self.handler.recordingResolutions[0] = (320, 240)
        self.handler.cameraHandles[0] = MagicMock()

        writer = MagicMock()
        self.handler.recordingOutputs[0] = writer
        self.handler.recordFileNames[0] = "records/test.mp4"

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        self.handler.publishFrame(frame, self.handle)

        written = writer.write.call_args[0][0]
        self.assertEqual(written.shape, (240, 320, 3))
        self.assertIn(0, self.handler._recordFrameBuffers)

        # Stopping recording should free the cached destination buffer.
        self.handler.recordingStatus[0] = False
        self.handler.publishFrame(frame, self.handle)
        self.assertNotIn(0, self.handler._recordFrameBuffers)


if __name__ == "__main__":
    unittest.main()
