# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import tempfile
import threading
# test_file_server.py
from pathlib import Path

import pytest
import requests
from synapse_net.file_server import FileServer


# -------------------------
# Helper: start server in background for tests
# -------------------------
@pytest.fixture
def server():
    with tempfile.TemporaryDirectory() as tmpdir:
        files_dir = Path(tmpdir)
        srv = FileServer(
            files_dir, host="127.0.0.1", port=0
        )  # port=0 -> random free port
        srv.start()

        # Wait for thread to start
        threading.Event().wait(0.1)

        yield srv

        srv.stop()


# -------------------------
# Helper: get server URL
# -------------------------
def server_url(srv: FileServer) -> str:
    host, port = srv._server.server_address  # pyright: ignore
    return f"http://{host}:{port}"


# -------------------------
# Test: OPTIONS request
# -------------------------
def test_options(server):
    url = server_url(server)
    resp = requests.options(url)
    assert resp.status_code == 200
    assert resp.headers["Access-Control-Allow-Origin"] == "*"
    assert "GET" in resp.headers["Access-Control-Allow-Methods"]


# -------------------------
# Test: upload file via POST
# -------------------------
def test_file_upload(server):
    url = server_url(server)
    files = {"file": ("test.txt", b"hello world")}
    resp = requests.post(url, files=files)
    assert resp.status_code == 200
    assert resp.content == b"Upload successful"

    # Confirm file saved
    saved_file = server.files_dir / "test.txt"
    assert saved_file.exists()
    assert saved_file.read_bytes() == b"hello world"


# -------------------------
# Test: download file via GET
# -------------------------
def test_file_download(server):
    # Create a file
    test_file = server.files_dir / "download.txt"
    test_file.write_bytes(b"download content")

    url = server_url(server) + "/download.txt"
    resp = requests.get(url)
    assert resp.status_code == 200
    assert resp.content == b"download content"


# -------------------------
# Test: POST without multipart
# -------------------------
def test_post_non_multipart(server):
    url = server_url(server)
    resp = requests.post(url, data={"foo": "bar"})
    assert resp.status_code == 400
    assert b"not multipart/form-data" in resp.content


# -------------------------
# Test: start/stop server
# -------------------------
def test_server_start_stop():
    with tempfile.TemporaryDirectory() as tmpdir:
        srv = FileServer(Path(tmpdir))
        srv.start()
        assert srv._thread.is_alive()  # pyright: ignore
        assert srv._server is not None
        srv.stop()
        assert not srv._thread.is_alive()  # pyright: ignore
