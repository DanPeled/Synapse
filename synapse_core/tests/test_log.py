# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import re
import sys
from typing import List, Tuple
from unittest.mock import patch

import pytest
import synapse.log as log
from synapse_net.generated.messages.v1 import AlertTypeProto, LogLevelProto


class FakeClock:
    def __init__(self, value: float = 1000.0):
        self.value = value

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


class RecordingSink:
    def __init__(self):
        self.records: List[Tuple[log.LogRecord, str]] = []

    def __call__(self, record: log.LogRecord, formatted: str) -> None:
        self.records.append((record, formatted))


@pytest.fixture
def cleanupLogs() -> None:
    log.flushLogs()
    log.closeLogHandle()
    for f in os.listdir("logs"):
        if f.startswith("logfile_"):
            os.remove(os.path.join("logs", f))


def test_log_creates_file_and_logs_text(cleanupLogs) -> None:
    test_message = "Test log message"
    log.info(test_message)
    log.flushLogs()

    log_files = [f for f in os.listdir("logs") if f.startswith("logfile_")]
    assert log_files, "No log files created"

    log_path = os.path.join("logs", log_files[0])
    with open(log_path, "r") as f:
        contents = f.read()
        assert test_message in contents
        assert re.search(r"\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}]:", contents)


def test_err_logs_error_with_formatting(cleanupLogs) -> None:
    test_error = "Something went wrong"
    log.err(test_error)
    log.flushLogs()

    log_files = [f for f in os.listdir("logs") if f.startswith("logfile_")]
    log_path = os.path.join("logs", log_files[0])

    with open(log_path, "r") as f:
        contents = f.read()
        assert "[ERROR]" in contents
        assert test_error in contents

        assert "[red]" in contents
        assert "[/red]" in contents


def test_stderr_redirection() -> None:
    captured = []

    class CaptureStderr:
        def write(self, data):
            captured.append(data)

    sys_err_backup = sys.stderr
    sys.stderr = CaptureStderr()

    print("Error to stderr", file=sys.stderr)
    sys.stderr = sys_err_backup

    assert any("Error to stderr" in c for c in captured)


def test_duplicate_records_are_suppressed_until_summary() -> None:
    clock = FakeClock()
    sink = RecordingSink()
    dispatcher = log.LogDispatcher(sink=sink, clock=clock, summaryInterval=10.0)
    try:
        dispatcher.submit(LogLevelProto.INFO, "repeated message")
        dispatcher.flush()
        assert len(sink.records) == 1

        for _ in range(5):
            clock.advance(1.0)
            dispatcher.submit(LogLevelProto.INFO, "repeated message")
        dispatcher.flush()
        assert len(sink.records) == 1

        clock.advance(10.0)
        dispatcher.submit(LogLevelProto.INFO, "repeated message")
        dispatcher.flush()
        assert len(sink.records) == 2

        record, formatted = sink.records[-1]
        assert "suppressed 5 duplicate(s)" in record.message
        assert record.isSummary
        assert record.alertType is None
        assert "suppressed 5 duplicate(s)" in formatted
    finally:
        dispatcher.stop()


def test_duplicate_after_a_quiet_interval_is_reported_again() -> None:
    clock = FakeClock()
    sink = RecordingSink()
    dispatcher = log.LogDispatcher(sink=sink, clock=clock, summaryInterval=5.0)
    try:
        dispatcher.submit(LogLevelProto.INFO, "spaced message")
        dispatcher.flush()
        assert len(sink.records) == 1

        clock.advance(10.0)
        dispatcher.submit(LogLevelProto.INFO, "spaced message")
        dispatcher.flush()
        assert len(sink.records) == 2
        assert not sink.records[-1][0].isSummary
    finally:
        dispatcher.stop()


def test_alerting_record_with_same_text_is_not_swallowed() -> None:
    clock = FakeClock()
    sink = RecordingSink()
    dispatcher = log.LogDispatcher(sink=sink, clock=clock, summaryInterval=10.0)
    try:
        dispatcher.submit(LogLevelProto.INFO, "important")
        dispatcher.submit(LogLevelProto.INFO, "important", AlertTypeProto.INFO)
        dispatcher.flush()

        assert [record.alertType for record, _ in sink.records] == [
            None,
            AlertTypeProto.INFO,
        ]
    finally:
        dispatcher.stop()


def test_duplicate_summary_is_emitted_on_flush_when_no_new_record() -> None:
    clock = FakeClock()
    sink = RecordingSink()
    dispatcher = log.LogDispatcher(sink=sink, clock=clock, summaryInterval=5.0)
    try:
        dispatcher.submit(LogLevelProto.INFO, "quiet duplicate")
        for _ in range(3):
            clock.advance(1.0)
            dispatcher.submit(LogLevelProto.INFO, "quiet duplicate")
        dispatcher.flush()
        assert len(sink.records) == 1

        clock.advance(5.0)
        dispatcher.flush()
        assert len(sink.records) == 2
        assert "suppressed 3 duplicate(s)" in sink.records[-1][0].message

        dispatcher.flush()
        assert len(sink.records) == 2
    finally:
        dispatcher.stop()


def test_same_message_at_different_levels_is_not_deduplicated() -> None:
    clock = FakeClock()
    sink = RecordingSink()
    dispatcher = log.LogDispatcher(sink=sink, clock=clock, summaryInterval=10.0)
    try:
        dispatcher.submit(LogLevelProto.INFO, "same text")
        dispatcher.submit(LogLevelProto.WARNING, "same text")
        dispatcher.flush()

        assert [record.level for record, _ in sink.records] == [
            LogLevelProto.INFO,
            LogLevelProto.WARNING,
        ]
    finally:
        dispatcher.stop()


def test_err_alert_is_deduplicated_with_the_log_record() -> None:
    clock = FakeClock()
    sink = RecordingSink()
    dispatcher = log.LogDispatcher(sink=sink, clock=clock, summaryInterval=10.0)
    original = log._dispatcher
    log._dispatcher = dispatcher
    try:
        log.err("repeated error")
        log.err("repeated error")
        dispatcher.flush()

        assert len(sink.records) == 1
        record, formatted = sink.records[0]
        assert record.level == LogLevelProto.ERROR
        assert record.alertType == AlertTypeProto.ERROR
        assert "[ERROR]: repeated error" in record.message
        assert "[ERROR]: repeated error" in formatted
    finally:
        log._dispatcher = original
        dispatcher.stop()


def test_default_sink_does_not_send_a_log_message_for_an_alert() -> None:
    record = log.LogRecord(
        level=LogLevelProto.ERROR,
        message="[ERROR]: boom",
        alertType=AlertTypeProto.ERROR,
        timestamp=123.0,
    )

    with (
        patch.object(log, "_writeLogLine") as writeLine,
        patch.object(log, "_sendSocketLog") as sendSocketLog,
        patch.object(log, "alert") as sendAlert,
    ):
        log._defaultLogSink(record, "formatted error")

    writeLine.assert_called_once_with("formatted error")
    sendSocketLog.assert_not_called()
    sendAlert.assert_called_once_with(AlertTypeProto.ERROR, "formatted error")


def test_default_sink_still_sends_plain_log_messages() -> None:
    record = log.LogRecord(
        level=LogLevelProto.INFO,
        message="plain message",
        timestamp=123.0,
    )

    with (
        patch.object(log, "_writeLogLine"),
        patch.object(log, "_sendSocketLog") as sendSocketLog,
        patch.object(log, "alert") as sendAlert,
    ):
        log._defaultLogSink(record, "formatted message")

    sendAlert.assert_not_called()
    sendSocketLog.assert_called_once_with(
        "formatted message", LogLevelProto.INFO, log.WebSocketServer.kInstance, 123.0
    )


def test_exception_throttle_is_per_camera_and_lazily_formats_tracebacks() -> None:
    clock = FakeClock()
    throttle = log.ExceptionThrottle(interval=10.0, clock=clock)

    def failIfFormatted() -> str:
        pytest.fail("traceback should not be formatted for suppressed exceptions")

    first = throttle.exceptionDetail(0, RuntimeError("boom"), lambda: "FULL TRACEBACK")
    assert first == "FULL TRACEBACK"

    for _ in range(3):
        clock.advance(1.0)
        assert (
            throttle.exceptionDetail(0, RuntimeError("boom"), failIfFormatted) is None
        )

    assert (
        throttle.exceptionDetail(1, RuntimeError("other"), lambda: "OTHER TRACEBACK")
        == "OTHER TRACEBACK"
    )

    clock.advance(10.0)
    summary = throttle.exceptionDetail(0, RuntimeError("latest"), failIfFormatted)
    assert summary is not None
    assert "3 additional exception(s) suppressed" in summary
    assert "RuntimeError: latest" in summary


def test_throttle_starts_a_new_full_report_after_a_quiet_gap() -> None:
    clock = FakeClock()
    throttle = log.ExceptionThrottle(interval=10.0, clock=clock)

    assert (
        throttle.exceptionDetail(0, RuntimeError("first"), lambda: "TRACEBACK 1")
        == "TRACEBACK 1"
    )
    clock.advance(20.0)
    assert (
        throttle.exceptionDetail(0, RuntimeError("again"), lambda: "TRACEBACK 2")
        == "TRACEBACK 2"
    )


def test_dispatcher_does_not_block_when_queue_is_full() -> None:
    sink = RecordingSink()
    dispatcher = log.LogDispatcher(sink=sink, maxQueueSize=1, clock=FakeClock())
    try:
        for index in range(20):
            dispatcher.submit(LogLevelProto.INFO, f"message {index}")
        assert dispatcher.droppedRecords > 0
    finally:
        dispatcher.stop()
