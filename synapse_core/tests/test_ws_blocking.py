# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Regression tests for offloaded websocket dispatch and debounced saves."""

from pathlib import Path
from typing import List
from unittest.mock import MagicMock, patch

from synapse.core.command_dispatcher import CommandDispatcher
from synapse.core.runtime_handler import RuntimeManager
from synapse.core.synapse import Synapse
from synapse_net.generated.messages.v1 import (
    LogLevelProto,
    MessageProto,
    MessageTypeProto,
    RemovePipelineMessageProto,
)


def makeRuntimeManager() -> RuntimeManager:
    with patch("synapse.core.runtime_handler.CameraHandler", return_value=MagicMock()):
        return RuntimeManager(directory=Path("."))


def test_command_dispatcher_preserves_order() -> None:
    processed: List[int] = []
    errors: List[Exception] = []
    dispatcher = CommandDispatcher[int](
        processed.append,
        lambda error: errors.append(error),
    )

    dispatcher.start()
    for index in range(50):
        dispatcher.submit(index)
    dispatcher.stop()

    assert processed == list(range(50))
    assert errors == []


def test_command_dispatcher_reports_handler_errors() -> None:
    errors: List[Exception] = []

    def fail(command: str) -> None:
        raise ValueError(command)

    dispatcher = CommandDispatcher[str](fail, lambda error: errors.append(error))
    dispatcher.start()
    dispatcher.submit("bad command")
    dispatcher.stop()

    assert [str(error) for error in errors] == ["bad command"]


def test_queue_message_parses_on_caller_and_enqueues() -> None:
    synapse = object.__new__(Synapse)
    synapse._commandDispatcher = MagicMock()
    synapse.websocket = MagicMock()

    message = MessageProto(
        type=MessageTypeProto.DELETE_PIPELINE,
        remove_pipeline=RemovePipelineMessageProto(remove_pipeline_index=2, cameraid=1),
    )
    synapse.queueMessage("client", message.SerializeToString())

    dispatcher = synapse._commandDispatcher
    assert dispatcher is not None
    dispatcher.submit.assert_called_once()
    client, parsed = dispatcher.submit.call_args.args[0]
    assert client == "client"
    assert parsed.type == MessageTypeProto.DELETE_PIPELINE
    assert parsed.remove_pipeline.remove_pipeline_index == 2
    assert parsed.remove_pipeline.cameraid == 1


def test_queue_message_reports_parse_errors_without_dispatch() -> None:
    synapse = object.__new__(Synapse)
    synapse._commandDispatcher = MagicMock()
    synapse.websocket = MagicMock()

    with patch("synapse.core.synapse.socketLog") as socketLog:
        synapse.queueMessage("client", b"not a valid protobuf")

    dispatcher = synapse._commandDispatcher
    assert dispatcher is not None
    dispatcher.submit.assert_not_called()
    assert socketLog.call_args.args[1] == LogLevelProto.ERROR


def test_save_requests_are_debounced_and_flushed() -> None:
    manager = makeRuntimeManager()
    manager._saveDebounceSeconds = 0.05
    manager.saveNow = MagicMock()

    try:
        for _ in range(20):
            manager.save()
        # No write happens on the caller and the burst is coalesced.
        assert manager.saveNow.call_count == 0
        manager.stopSaveWorker()
        assert manager.saveNow.call_count == 1
    finally:
        manager.stopSaveWorker()


def test_cancelled_saves_do_not_recreate_deleted_config() -> None:
    manager = makeRuntimeManager()
    manager._saveDebounceSeconds = 0.05
    manager.saveNow = MagicMock()

    try:
        manager.save()
        manager.cancelPendingSaves()
        manager.save()
        assert manager.saveNow.call_count == 0
    finally:
        manager.stopSaveWorker(flush=False)


def test_save_failures_are_reported_to_callback() -> None:
    manager = makeRuntimeManager()
    manager._saveDebounceSeconds = 0.01
    manager.saveNow = MagicMock(side_effect=OSError("disk full"))
    errors: List[Exception] = []
    manager.onSaveError.add(lambda error: errors.append(error))

    try:
        manager.save()
        manager.stopSaveWorker()
        assert len(errors) == 1
        assert isinstance(errors[0], OSError)
    finally:
        manager.stopSaveWorker()


def test_atomic_write_replaces_existing_file(tmp_path: Path) -> None:
    from synapse.core.runtime_handler import _atomicWriteText

    target = tmp_path / "settings.yml"
    target.write_text("old value", encoding="utf-8")

    _atomicWriteText(target, "new value")

    assert target.read_text(encoding="utf-8") == "new value"
    assert list(tmp_path.glob("*.tmp")) == []


def test_on_message_still_dispatches_serialized_commands() -> None:
    synapse = object.__new__(Synapse)
    synapse.runtimeHandler = MagicMock()
    synapse.websocket = MagicMock()

    message = MessageProto(
        type=MessageTypeProto.DELETE_PIPELINE,
        remove_pipeline=RemovePipelineMessageProto(remove_pipeline_index=2, cameraid=3),
    )
    synapse.onMessage(None, message.SerializeToString())

    removePipeline = synapse.runtimeHandler.pipelineHandler.removePipeline
    removePipeline.assert_called_once_with(2, 3)
