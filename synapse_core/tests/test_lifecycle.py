# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import threading
import time
from unittest.mock import MagicMock, patch

import pytest
from synapse.core.lifecycle import ShutdownStack, joinThread


def test_shutdown_runs_callbacks_in_reverse_order():
    stack = ShutdownStack()
    calls = []

    stack.register("first", lambda: calls.append("first"))
    stack.register("second", lambda: calls.append("second"))
    stack.register("third", lambda: calls.append("third"))

    stack.shutdown()

    assert calls == ["third", "second", "first"]


def test_shutdown_logs_each_resource():
    stack = ShutdownStack()
    stack.register("camera handler", lambda: None)
    stack.register("pipeline handler", lambda: None)

    with patch("synapse.core.lifecycle.log.info") as info:
        stack.shutdown()

    info.assert_any_call("Shutting down pipeline handler...")
    info.assert_any_call("Shutting down camera handler...")


def test_shutdown_is_idempotent():
    stack = ShutdownStack()
    callback = MagicMock()
    stack.register("resource", callback)

    stack.shutdown()
    stack.shutdown()

    callback.assert_called_once()


def test_shutdown_continues_after_callback_error():
    stack = ShutdownStack()
    calls = []

    def failing():
        calls.append("failing")
        raise RuntimeError("boom")

    stack.register("first", lambda: calls.append("first"))
    stack.register("failing", failing)
    stack.register("last", lambda: calls.append("last"))

    with patch("synapse.core.lifecycle.log.err") as error:
        stack.shutdown()

    assert calls == ["last", "failing", "first"]
    error.assert_called_once()


def test_register_after_shutdown_raises():
    stack = ShutdownStack()
    stack.shutdown()

    with pytest.raises(RuntimeError, match="shutdown has already started"):
        stack.register("late", lambda: None)


def test_concurrent_shutdown_waits_for_completion():
    stack = ShutdownStack()
    release = threading.Event()
    entered = threading.Event()
    finished = []

    def slow():
        entered.set()
        release.wait(timeout=5)

    stack.register("slow", slow)
    first = threading.Thread(
        target=lambda: (stack.shutdown(), finished.append("first"))
    )
    first.start()
    assert entered.wait(timeout=5)

    secondDone = threading.Event()
    second = threading.Thread(
        target=lambda: (stack.shutdown(), finished.append("second"), secondDone.set())
    )
    second.start()
    time.sleep(0.05)
    assert not secondDone.is_set(), "second shutdown returned before cleanup finished"

    release.set()
    first.join(timeout=5)
    second.join(timeout=5)
    assert secondDone.is_set()
    assert finished == ["first", "second"]


def test_join_thread_ignores_missing_thread():
    assert joinThread(None, "missing", 0.1)


def test_join_thread_reports_unstoppable_thread():
    thread = MagicMock()
    thread.is_alive.return_value = True

    with patch("synapse.core.lifecycle.log.warn") as warning:
        assert not joinThread(thread, "stuck", 0.1)

    thread.join.assert_called_once_with(0.1)
    warning.assert_called_once()
