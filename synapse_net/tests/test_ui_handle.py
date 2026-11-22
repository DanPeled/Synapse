# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import threading
import types
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer
from threading import Thread

import requests
from synapse_net.ui_handle import (
    MultiHTMLHandler,
    ReusableThreadingHTTPServer,
    UIHandle,
)


def test_ui_server_is_threaded_with_daemon_threads():
    assert issubclass(ReusableThreadingHTTPServer, ThreadingHTTPServer)
    assert ReusableThreadingHTTPServer.allow_reuse_address is True
    assert ReusableThreadingHTTPServer.daemon_threads is True
    assert ReusableThreadingHTTPServer.block_on_close is False


def test_startUI_logs_error_when_module_missing(monkeypatch):
    logged = []

    monkeypatch.setattr(
        "importlib.util.find_spec",
        lambda name: None,
    )
    monkeypatch.setattr(
        "synapse_net.ui_handle.info",
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
        "synapse_net.ui_handle.info",
        lambda *_: None,
    )

    UIHandle.startUI(3000)

    assert started["thread"] is True


def test_startUI_handles_concurrent_requests(monkeypatch, tmp_path):
    captured = {}
    ready = threading.Event()
    threads: list[Thread] = []

    class CapturingServer(ReusableThreadingHTTPServer):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            captured["server"] = self
            ready.set()

    class CapturingThread(Thread):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            threads.append(self)

    monkeypatch.setattr(
        "synapse_net.ui_handle.ReusableThreadingHTTPServer", CapturingServer
    )
    monkeypatch.setattr("synapse_net.ui_handle.Thread", CapturingThread)
    monkeypatch.setattr(
        "importlib.util.find_spec",
        lambda name: types.SimpleNamespace(origin=str(tmp_path / "__init__.py")),
    )
    monkeypatch.setattr("synapse_net.ui_handle.getIP", lambda: "127.0.0.1")
    monkeypatch.setattr("synapse_net.ui_handle.info", lambda *_: None)

    # Both requests must enter the handler before either completes; a
    # single-threaded server would leave the barrier waiting for a second
    # connection that it cannot accept.
    barrier = threading.Barrier(2, timeout=3)

    def slow_get(handler):
        barrier.wait()
        handler.send_response(200)
        handler.end_headers()
        handler.wfile.write(b"ok")

    monkeypatch.setattr(MultiHTMLHandler, "do_GET", slow_get)

    UIHandle.startUI(0)

    assert ready.wait(2)
    server = captured["server"]
    port = server.server_address[1]

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(requests.get, f"http://127.0.0.1:{port}/{index}")
                for index in range(2)
            ]
            responses = [future.result(timeout=5) for future in futures]

        assert [response.status_code for response in responses] == [200, 200]
    finally:
        server.shutdown()
        for thread in threads:
            thread.join(timeout=2)
