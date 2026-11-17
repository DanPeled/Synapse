# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

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
