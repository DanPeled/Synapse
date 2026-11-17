# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import numpy as np
from ntcore import ValueEventData
from synapse import Pipeline, PipelineSettings
from synapse.core.pipeline import FrameResult, PipelineResult
from synapse.core.runtime_handler import RuntimeManager


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

    def test_get_event_data_value_bool(self):
        mock_event = MagicMock()
        type_prop = PropertyMock(return_value="Boolean")
        value = MagicMock(getBoolean=MagicMock(return_value=True))
        mock_event.data.__class__ = ValueEventData
        mock_event.data.topic.getType = type_prop
        mock_event.data.value = value

        with patch("synapse.core.runtime_handler.NetworkTableType.kBoolean", "Boolean"):
            result = self.handler.getEventDataValue(mock_event)
            self.assertTrue(result)

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

    def test_request_stop_clears_running_event(self):
        self.handler.running.set()

        self.handler.requestStop()

        self.assertFalse(self.handler.running.is_set())
        self.assertTrue(self.handler.stopped.is_set())

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
        versionPublisher = MagicMock()
        self.handler.propPubs[(0, "setting")] = publisher
        self.handler.versionPublisher = versionPublisher
        self.handler._ntListeners = [10, 11]

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
        self.assertIsNone(self.handler.versionPublisher)
        nt.getDefault.return_value.removeListener.assert_any_call(10)
        nt.getDefault.return_value.removeListener.assert_any_call(11)
        publisher.close.assert_called_once()
        versionPublisher.close.assert_called_once()
        pipelineCleanup.assert_called_once()
        self.mock_camera_handler.cleanup.assert_called_once()
        self.assertFalse(self.handler.isSetup)

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
