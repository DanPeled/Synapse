# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import types

from synapse_net.ui_handle import UIHandle


def test_startUI_logs_error_when_module_missing(monkeypatch):
    logged = []

    monkeypatch.setattr(
        "importlib.util.find_spec",
        lambda name: None,
    )
    monkeypatch.setattr(
        "synapse_net.ui_handle.log",
        lambda msg: logged.append(msg),
    )

    UIHandle.startUI(3000)

    assert any("synapse_ui module not found" in m for m in logged)


def test_startUI_starts_thread_when_module_exists(monkeypatch, tmp_path):
    started = {"thread": False}

    fake_spec = types.SimpleNamespace(origin=str(tmp_path / "__init__.py"))

    class FakeThread:
        def __init__(self, target, daemon):
            started["thread"] = True
            self.target = target
            self.daemon = daemon

        def start(self):
            pass

    monkeypatch.setattr(
        "importlib.util.find_spec",
        lambda name: fake_spec,
    )
    monkeypatch.setattr(
        "synapse_net.ui_handle.Thread",
        FakeThread,
    )
    monkeypatch.setattr(
        "synapse_net.ui_handle.log",
        lambda *_: None,
    )

    UIHandle.startUI(3000)

    assert started["thread"] is True
