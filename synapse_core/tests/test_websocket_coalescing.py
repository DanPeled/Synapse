# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock, patch

import synapse.log as log
from synapse.core.runtime_handler import RuntimeManager
from synapse.core.synapse import Synapse
from synapse_net.generated.messages.v1 import (
    LogLevelProto,
    MessageProto,
    MessageTypeProto,
)
from synapse_net.socketServer import WebSocketServer


def resolvePayload(payload: Any) -> bytes:
    """Resolve the lazy builders used for coalesced messages."""
    resolved = payload() if callable(payload) else payload
    return cast(bytes, resolved)


def makeRuntimeManager() -> tuple[RuntimeManager, MagicMock]:
    cameraHandler = MagicMock()
    with patch(
        "synapse.core.runtime_handler.CameraHandler", return_value=cameraHandler
    ):
        manager = RuntimeManager(directory=Path("."))
    return manager, cameraHandler


def test_socket_log_coalesces_by_level() -> None:
    socket = MagicMock()

    log.socketLog("first", LogLevelProto.INFO, socket)
    log.socketLog("second", LogLevelProto.INFO, socket)
    log.socketLog("warning", LogLevelProto.WARNING, socket)

    calls = socket.sendToAllSync.call_args_list
    assert [call.kwargs["coalesce_key"] for call in calls] == [
        ("log", LogLevelProto.INFO),
        ("log", LogLevelProto.INFO),
        ("log", LogLevelProto.WARNING),
    ]

    messages = [MessageProto().parse(resolvePayload(call.args[0])) for call in calls]
    assert [message.log.message for message in messages] == [
        "first",
        "second",
        "warning",
    ]
    assert [message.log.level for message in messages] == [
        LogLevelProto.INFO,
        LogLevelProto.INFO,
        LogLevelProto.WARNING,
    ]


def test_camera_performance_is_coalesced_per_camera() -> None:
    manager, cameraHandler = makeRuntimeManager()
    cameraHandler.getCameraHandle.return_value = "handle"
    table = MagicMock()
    ws = MagicMock()

    with (
        patch("synapse.core.runtime_handler.getCameraTable", return_value=table),
        patch.object(WebSocketServer, "kInstance", ws),
    ):
        manager.sendLatency(1, 0.1, 0.2, 30)
        manager.sendLatency(2, 0.1, 0.2, 30)

    calls = ws.sendToAllSync.call_args_list
    assert [call.kwargs["coalesce_key"] for call in calls] == [
        ("camera_performance", 1),
        ("camera_performance", 2),
    ]

    for call, cameraIndex in zip(calls, (1, 2)):
        message = MessageProto().parse(resolvePayload(call.args[0]))
        assert message.type == MessageTypeProto.REPORT_CAMERA_PERFORMANCE
        assert message.camera_performance.camera_index == cameraIndex


def test_metrics_use_a_single_coalesce_key() -> None:
    manager, _ = makeRuntimeManager()
    ws = MagicMock()
    metricsManager = MagicMock()
    metricsManager.getCpuTemp.return_value = 41.0
    metricsManager.getCpuUtilization.return_value = 42.0
    metricsManager.getMemory.return_value = 43.0
    metricsManager.getUptime.return_value = 44.0
    metricsManager.getGPUMemorySplit.return_value = 45.0
    metricsManager.getUsedRam.return_value = 46.0
    metricsManager.getUsedDiskPct.return_value = 47.0
    metricsManager.getNpuUsage.return_value = 48.0

    def stopWorker(timeout=None):
        manager.running.clear()
        return True

    with (
        patch("synapse.hardware.metrics.MetricsManager", return_value=metricsManager),
        patch("synapse.core.runtime_handler.NetworkTableInstance"),
        patch.object(WebSocketServer, "kInstance", ws),
        patch.object(manager.stopped, "wait", side_effect=stopWorker),
    ):
        manager.startMetricsThread()
        assert manager.metricsThread is not None
        manager.metricsThread.join(timeout=2)

    assert manager.metricsThread is not None
    assert not manager.metricsThread.is_alive()

    # The startup log message also uses the websocket; only the metrics
    # payloads are coalesced under the metrics key.
    metricCalls = [
        call
        for call in ws.sendToAllSync.call_args_list
        if call.kwargs.get("coalesce_key") == ("metrics",)
    ]
    assert len(metricCalls) == 1

    call = metricCalls[0]
    message = MessageProto().parse(resolvePayload(call.args[0]))
    assert message.type == MessageTypeProto.SEND_METRICS
    assert message.hardware_metrics.cpu_temp == 41.0
    assert message.hardware_metrics.cpu_usage == 42.0


def test_setting_updates_are_coalesced_per_setting() -> None:
    synapse = object.__new__(Synapse)
    synapse.runtimeHandler = MagicMock()
    synapse.runtimeHandler.pipelineBindings = {2: 7}
    synapse.ntClient = MagicMock()
    synapse.websocket = MagicMock()

    with patch.object(Synapse, "kInstance", synapse, create=True):
        synapse.setupRuntimeCallbacks()
        onSettingChanged = (
            synapse.runtimeHandler.onSettingChangedFromNT.add.call_args.args[0]
        )
        onSettingChanged("brightness", 5, 2)

    ws = synapse.websocket
    ws.sendToAllSync.assert_called_once()

    call = ws.sendToAllSync.call_args
    assert call.kwargs["coalesce_key"] == ("setting", 2, 7, "brightness")
    message = MessageProto().parse(resolvePayload(call.args[0]))
    assert message.type == MessageTypeProto.SET_SETTING
    assert message.set_pipeline_setting.cameraid == 2
    assert message.set_pipeline_setting.pipeline_index == 7
    assert message.set_pipeline_setting.setting == "brightness"
