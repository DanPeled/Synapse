# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import threading

from synapse.callback import Callback


def test_add_and_call_callback():
    called = []

    def cb(a, b):
        called.append((a, b))

    callback = Callback[[int, int]]()
    callback.add(cb)

    callback(1, 2)
    assert called == [(1, 2)]


def test_remove_callback():
    called = []

    def cb(x):
        called.append(x)

    callback = Callback[[int]]()
    callback.add(cb)
    callback.remove(cb)

    callback(5)  # Should not call anything
    assert called == []


def test_callback_with_kwargs():
    called = {}

    def cb(x=None):
        called["x"] = x

    callback = Callback[int]()
    callback.add(cb)
    callback(42)

    assert called["x"] == 42


def test_callback_can_modify_registration_while_dispatching():
    """Dispatch uses a snapshot, so add/remove during a call is safe."""
    callback = Callback[int]()
    seen = []

    def remover(value):
        seen.append(value)
        callback.remove(remover)
        callback.add(lambda v: seen.append(v + 100))

    callback.add(remover)
    callback(1)

    assert seen == [1]
    callback(2)
    assert seen == [1, 102]


def test_concurrent_registration_and_dispatch():
    """Registration from another thread must not break an in-flight dispatch."""
    callback = Callback[int]()
    seen = []
    barrier = threading.Barrier(3)

    def reader():
        barrier.wait()
        for _ in range(200):
            callback(1)

    def writer():
        barrier.wait()
        for value in range(200):
            callback.add(lambda v, value=value: seen.append(value))

    callback.add(lambda value: seen.append(value))
    threads = [threading.Thread(target=reader), threading.Thread(target=writer)]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join(timeout=5)
        assert not thread.is_alive()

    assert len(seen) >= 200
