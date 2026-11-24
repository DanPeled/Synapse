# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, call, patch

import cv2
import numpy as np
import pytest
from ntcore import ValueEventData
from synapse import Pipeline, PipelineSettings
from synapse.core.pipeline import FrameResult, PipelineResult
from synapse.core.runtime_handler import RuntimeManager
from synapse.core.settings_api import CameraSettings
from synapse_net.socketServer import WebSocketServer


class DummyPipeline(Pipeline[PipelineSettings, PipelineResult]):
    __is_enabled__ = True

    def __init__(self, settings: PipelineSettings):
        super().__init__(settings)

    def processFrame(self, img, timestamp: float) -> FrameResult:
        pass


class DummySettings(PipelineSettings):
    def __init__(self, config_map=None):
        self.config_map = config_map or {}


class TestRuntimeManager(unittest.TestCase):
    def setUp(self):
        self.mock_camera_handler = MagicMock()

        with patch(
            "synapse.core.runtime_handler.CameraHandler",
            return_value=self.mock_camera_handler,
        ):
            self.handler = RuntimeManager(directory=Path("."))

    def test_assign_default_pipelines(self):
        self.mock_camera_handler.cameraHandles = {0: "Camera0", 1: "Camera1"}
        self.handler.pipelineHandler.getDefaultPipeline = MagicMock(
            side_effect=[10, 20]
        )
        self.handler.setPipelineByIndex = MagicMock()

        self.handler.assignDefaultPipelines()

        self.handler.setPipelineByIndex.assert_any_call(cameraIndex=0, pipelineIndex=10)
        self.handler.setPipelineByIndex.assert_any_call(cameraIndex=1, pipelineIndex=20)
        self.assertEqual(self.handler.setPipelineByIndex.call_count, 2)

    def test_set_pipeline_by_index_invalid_camera(self):
        self.mock_camera_handler.cameraHandles = {0: "Camera0"}
        self.handler.pipelineHandler.pipelineTypeNames = {0: {1: "PipelineA"}}

        with patch("synapse.core.runtime_handler.log.err") as mock_log:
            self.handler.setPipelineByIndex(cameraIndex=5, pipelineIndex=1)
            mock_log.assert_called_once()

    def test_pipeline_exceptions_are_throttled_per_camera(self):
        camera = MagicMock()
        camera.name = "Camera 0"
        self.mock_camera_handler.cameraHandles = {0: camera}
        self.handler.pipelineBindings = {0: 0}

        failingPipeline = MagicMock()
        failingPipeline.processFrame.side_effect = RuntimeError("boom")
        self.handler.pipelineHandler.getPipeline = MagicMock(
            return_value=failingPipeline
        )
        self.handler.sendLatency = MagicMock()
        frame = np.zeros((4, 4, 3), dtype=np.uint8)

        with patch("synapse.core.runtime_handler.log.err") as mock_log:
            for _ in range(100):
                self.handler._processAndPublishFrame(0, frame)

        mock_log.assert_called_once()
        assert "Camera 0" in mock_log.call_args.args[0]
        assert "RuntimeError: boom" in mock_log.call_args.args[0]

        # A second camera gets its own full first report.
        secondCamera = MagicMock()
        secondCamera.name = "Camera 1"
        self.mock_camera_handler.cameraHandles[1] = secondCamera
        self.handler.pipelineBindings[1] = 0

        with patch("synapse.core.runtime_handler.log.err") as mock_log:
            self.handler._processAndPublishFrame(1, frame)

        mock_log.assert_called_once()
        assert "Camera 1" in mock_log.call_args.args[0]

    def test_fixture_frame_reuses_rotation_destination(self):
        camera = MagicMock()
        self.mock_camera_handler.cameraHandles = {0: camera}
        settings = MagicMock()
        settings.getSetting.return_value = 90
        pipeline = MagicMock()
        pipeline.getCameraSettings.return_value = settings
        self.handler.pipelineBindings = {0: 0}
        self.handler.pipelineHandler.getPipeline = MagicMock(return_value=pipeline)

        frame = np.arange(4 * 6 * 3, dtype=np.uint8).reshape(4, 6, 3)
        first = self.handler.fixtureFrame(0, frame)
        second = self.handler.fixtureFrame(0, frame)

        settings.getSetting.assert_called_with(CameraSettings.orientation.key)
        assert first is second
        assert np.array_equal(first, cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE))

        settings.getSetting.return_value = 180
        rotatedAgain = self.handler.fixtureFrame(0, frame)
        assert np.array_equal(rotatedAgain, cv2.rotate(frame, cv2.ROTATE_180))

    def test_get_event_data_value_bool(self):
        mock_event = MagicMock()
        type_prop = PropertyMock(return_value="Boolean")
        value = MagicMock(getBoolean=MagicMock(return_value=True))
        mock_event.data.__class__ = ValueEventData
        mock_event.data.topic.getType = type_prop
        mock_event.data.value = value

        with patch("synapse.core.runtime_handler.NetworkTableType.BOOLEAN", "Boolean"):
            result = self.handler.getEventDataValue(mock_event)
            self.assertTrue(result)

    def test_send_latency_reuses_publishers(self):
        table = MagicMock()
        publishers = {}

        def getDoubleTopic(key):
            topic = MagicMock()
            topic.publish.return_value = publishers.setdefault(key, MagicMock())
            return topic

        table.getDoubleTopic.side_effect = getDoubleTopic
        self.mock_camera_handler.getCameraHandle.return_value = "handle"

        with (
            patch("synapse.core.runtime_handler.getCameraTable", return_value=table),
            patch.object(WebSocketServer, "kInstance", None),
        ):
            self.handler.sendLatency(0, 0.1, 0.2, 30)
            self.handler._lastLatencyReportTime.clear()
            self.handler.sendLatency(0, 0.1, 0.3, 30)

        assert table.getDoubleTopic.call_count == 2
        publishers["captureLatency"].set.assert_called_with(0.1)
        assert publishers["processLatency"].set.call_args_list[-1].args == (0.3,)

    def test_reported_fps_never_exceeds_camera_limit(self):
        """A short inter-frame gap must not report an impossible camera FPS."""
        camera = MagicMock()
        camera.getVideoMode.return_value.fps = 30
        camera.getMaxFPS.return_value = 30
        handle = MagicMock()
        handle.camera = camera
        self.mock_camera_handler.cameraHandles = {0: handle}
        self.handler.pipelineHandler.getPipeline = MagicMock(return_value=None)
        self.handler.sendLatency = MagicMock()
        self.handler.cameraHandler.publishFrame = MagicMock()

        clock = {"now": 900.0}
        frame = np.zeros((4, 4, 3), dtype=np.uint8)

        def reportedFps() -> int:
            return self.handler.cameraHandler.publishFrame.call_args.kwargs["fps"]

        with patch(
            "synapse.core.runtime_handler.time.perf_counter", lambda: clock["now"]
        ):
            for _ in range(30):
                clock["now"] += 1.0 / 30.0
                self.handler._processAndPublishFrame(0, frame)

            assert reportedFps() == pytest.approx(30, abs=1)

            # A burst after an idle period used to report 1 / 0.005 = 200 FPS.
            clock["now"] += 2.0
            self.handler._processAndPublishFrame(0, frame)
            clock["now"] += 0.005
            self.handler._processAndPublishFrame(0, frame)

            assert reportedFps() <= 30
            assert self.handler.sendLatency.call_args.args[-1] <= 30

            # Slow pipelines lower the rate rather than being masked by the cap.
            self.handler._frameRateMeters[0].reset()
            for _ in range(3):
                clock["now"] += 0.25
                self.handler._processAndPublishFrame(0, frame)
            assert reportedFps() <= 5

    def test_setup_calls_all_components(self):
        with (
            patch.object(self.handler.pipelineHandler, "setup") as setup_loader,
            patch.object(self.handler.cameraHandler, "setup") as setup_cameras,
            patch.object(self.handler, "assignDefaultPipelines") as assign_defaults,
            patch.object(self.handler, "setupNetworkTables") as setup_nt,
            patch.object(self.handler, "startMetricsThread") as start_metrics,
        ):
            self.handler.setup(directory=Path("."), sendSettingsInNT=False)

            setup_loader.assert_called_once()
            setup_cameras.assert_called_once()
            assign_defaults.assert_called_once()
            setup_nt.assert_called_once()
            start_metrics.assert_called_once()
            self.assertTrue(self.handler.isSetup)
            self.assertTrue(self.handler.setupEvent.is_set())

    def _runMetricsCycles(self, ws, clocks, cycles):
        """Run the metrics worker for a fixed number of fake cycles."""
        metrics = MagicMock()
        metrics.getCpuTemp.return_value = 41.0
        metrics.sampleCpuUtilization.return_value = 12.5
        metrics.getMemory.return_value = 8192
        metrics.getUptime.return_value = 1234.0
        metrics.getGPUMemorySplit.return_value = 0
        metrics.getUsedRam.return_value = 2048
        metrics.getUsedDiskPct.return_value = 55.0
        metrics.getNpuUsage.return_value = 0.0

        entry = MagicMock()
        nt = MagicMock()
        nt.getDoubleArrayTopic.return_value.publish.return_value = entry

        self.handler.running.set()
        waits = []

        def waitForNextCycle(delay):
            waits.append(delay)
            if len(waits) >= cycles:
                self.handler.running.clear()

        self.handler.stopped = MagicMock()
        self.handler.stopped.wait.side_effect = waitForNextCycle

        clockValues = iter(clocks)

        def nextClock():
            try:
                return next(clockValues)
            except StopIteration:
                return 1000.0

        with (
            patch(
                "synapse.core.runtime_handler.NetworkTableInstance.getDefault",
                return_value=nt,
            ),
            patch("synapse.hardware.metrics.MetricsManager", return_value=metrics),
            patch(
                "synapse.core.runtime_handler._metricsMonotonic",
                side_effect=nextClock,
            ),
            patch.object(WebSocketServer, "kInstance", ws),
            patch("synapse.core.runtime_handler.createMessage") as createMessage,
        ):
            self.handler.startMetricsThread()
            thread = self.handler.metricsThread
            assert thread is not None
            thread.join(timeout=2.0)

            self.assertFalse(thread.is_alive())
            self.handler.metricsThread = None

        return metrics, entry, waits, createMessage

    def test_metrics_thread_schedules_from_cycle_start(self):
        metrics, entry, waits, createMessage = self._runMetricsCycles(
            ws=None,
            clocks=[10.0, 10.2, 11.0, 11.3],
            cycles=2,
        )

        # Collection took 0.2 s and 0.3 s, so the wake is relative to each
        # cycle start instead of a fixed 1 s after collection finished.
        self.assertEqual(len(waits), 2)
        for actual, expected in zip(waits, [0.8, 0.7]):
            self.assertAlmostEqual(actual, expected)
        self.assertEqual(
            metrics.sampleCpuUtilization.call_args_list,
            [call(now=10.0), call(now=11.0)],
        )
        entry.set.assert_called_with([41.0, 12.5, 8192, 1234.0, 0, 2048, 55.0, 0.0])
        createMessage.assert_not_called()

    def test_metrics_thread_publishes_only_to_connected_clients(self):
        ws = MagicMock()
        ws.hasClients = True

        _, _, waits, createMessage = self._runMetricsCycles(
            ws=ws,
            clocks=[20.0, 20.05],
            cycles=1,
        )

        self.assertEqual(len(waits), 1)
        self.assertAlmostEqual(waits[0], 0.95)

        # Log records are now sent asynchronously by the logging writer, so
        # select the metrics payload instead of assuming it is the last send.
        metricCalls = [
            call_
            for call_ in ws.sendToAllSync.call_args_list
            if call_.kwargs.get("coalesce_key") == ("metrics",)
        ]
        assert len(metricCalls) == 1
        sendCall = metricCalls[0]
        payload = sendCall.args[0]
        assert callable(payload)
        with patch("synapse.core.runtime_handler.createMessage", createMessage):
            payload()
        createMessage.assert_called_once()
        ws.sendToAllSync.assert_any_call(payload, coalesce_key=("metrics",))

    def test_request_stop_clears_running_event(self):
        self.handler.running.set()

        self.handler.requestStop()

        self.assertFalse(self.handler.running.is_set())
        self.assertTrue(self.handler.stopped.is_set())

    def test_add_nt_listener_is_idempotent_by_key(self):
        entry = MagicMock()

        with patch(
            "synapse.core.runtime_handler.NetworkTableInstance.getDefault"
        ) as nt:
            nt.return_value.addListener.return_value = 10
            self.handler._addNtListener(
                entry, 1, lambda event: None, key=(0, "settings", "brightness")
            )
            self.handler._addNtListener(
                entry, 1, lambda event: None, key=(0, "settings", "brightness")
            )

        assert self.handler._ntListeners == [10]
        assert self.handler._ntListenerKeys == {(0, "settings", "brightness"): 10}

    def test_pipeline_nt_listener_binds_each_camera_index(self):
        self.mock_camera_handler.cameraHandles = {0: MagicMock(), 1: MagicMock()}
        self.handler.pipelineHandler.defaultPipelineIndexes = {0: 0, 1: 1}
        self.handler.setPipelineByIndex = MagicMock()
        self.handler.onPipelineChangedFromNT = MagicMock()

        with (
            patch(
                "synapse.core.runtime_handler.getCameraSettingEntry",
                return_value=MagicMock(),
            ),
            patch.object(self.handler, "_addNtListener") as addListener,
        ):
            self.handler.setupNetworkTables()

        callbacks = [call.args[2] for call in addListener.call_args_list]
        assert len(callbacks) == 2

        for cameraIndex, callback in enumerate(callbacks):
            event = MagicMock()
            event.data.__class__ = ValueEventData
            event.data.value.getInteger.return_value = 7
            callback(event)
            self.handler.setPipelineByIndex.assert_any_call(
                pipelineIndex=7, cameraIndex=cameraIndex
            )

    def test_run_blocks_until_stop_requested(self):
        thread = threading.Thread(target=self.handler.run, daemon=True)
        thread.start()

        thread.join(0.1)
        self.assertTrue(thread.is_alive())

        self.handler.requestStop()
        thread.join(1.0)
        self.assertFalse(thread.is_alive())

    def test_cleanup_stops_workers_and_releases_resources(self):
        self.handler.running.set()

        stopping = threading.Event()

        def worker():
            self.handler.stopped.wait()
            stopping.set()

        cameraThread = threading.Thread(target=worker, daemon=True)
        cameraThread.start()
        self.handler.cameraManagementThreads[0] = cameraThread

        metricsThread = threading.Thread(target=worker, daemon=True)
        metricsThread.start()
        self.handler.metricsThread = metricsThread

        publisher = MagicMock()
        latencyPublisher = MagicMock()
        versionPublisher = MagicMock()
        self.handler.propPubs[(0, "setting")] = publisher
        self.handler._latencyPubs[(0, "captureLatency")] = latencyPublisher
        self.handler.versionPublisher = versionPublisher
        self.handler._ntListeners = [10, 11]
        self.handler.setupEvent.set()

        with (
            patch("synapse.core.runtime_handler.NetworkTableInstance") as nt,
            patch.object(self.handler.pipelineHandler, "cleanup") as pipelineCleanup,
        ):
            self.handler.cleanup()

        self.assertFalse(self.handler.running.is_set())
        self.assertTrue(stopping.is_set())
        self.assertFalse(cameraThread.is_alive())
        self.assertFalse(metricsThread.is_alive())
        self.assertIsNone(self.handler.metricsThread)
        self.assertEqual(self.handler.cameraManagementThreads, {})
        self.assertEqual(self.handler._ntListeners, [])
        self.assertEqual(self.handler.propPubs, {})
        self.assertEqual(self.handler._latencyPubs, {})
        latencyPublisher.close.assert_called_once()
        self.assertIsNone(self.handler.versionPublisher)
        nt.getDefault.return_value.removeListener.assert_any_call(10)
        nt.getDefault.return_value.removeListener.assert_any_call(11)
        publisher.close.assert_called_once()
        versionPublisher.close.assert_called_once()
        pipelineCleanup.assert_called_once()
        self.mock_camera_handler.cleanup.assert_called_once()
        self.assertFalse(self.handler.isSetup)
        self.assertFalse(self.handler.setupEvent.is_set())

    def test_cleanup_is_idempotent(self):
        self.handler.cleanup()
        self.handler.cleanup()

        self.mock_camera_handler.cleanup.assert_called_once()


class TestHandleFramePublishing(unittest.TestCase):
    def setUp(self):
        self.mock_camera_handler = MagicMock()

        with patch(
            "synapse.core.runtime_handler.CameraHandler",
            return_value=self.mock_camera_handler,
        ):
            self.handler = RuntimeManager(directory=Path("."))

        self.frame = np.zeros((10, 10, 3), dtype=np.uint8)

    def test_returns_frame_for_default_view_id(self):
        entry = MagicMock()
        self.handler.cameraFrameEntries[0] = entry
        self.handler.cameraViewIDs[0] = self.handler.DEFAULT_STEP

        result = self.handler.handleFramePublishing(self.frame, 0)

        self.assertIs(result, self.frame)
        # The cached view id avoids any per-frame NetworkTables reads.
        entry.exists.assert_not_called()
        entry.getString.assert_not_called()

    def test_hides_frame_for_non_default_view_id(self):
        self.handler.cameraFrameEntries[0] = MagicMock()
        self.handler.cameraViewIDs[0] = "overlay"

        self.assertIsNone(self.handler.handleFramePublishing(self.frame, 0))

    def test_returns_none_for_missing_result(self):
        self.handler.cameraFrameEntries[0] = MagicMock()
        self.handler.cameraViewIDs[0] = self.handler.DEFAULT_STEP

        self.assertIsNone(self.handler.handleFramePublishing(None, 0))


if __name__ == "__main__":
    unittest.main()
