# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import io
import tempfile
import threading
import zipfile
from pathlib import Path
from urllib.parse import quote

import pytest
import requests
from synapse_net.file_server import FileServer


@pytest.fixture
def server():
    with tempfile.TemporaryDirectory() as tmpdir:
        files_dir = Path(tmpdir)
        srv = FileServer(files_dir, host="127.0.0.1", port=0)
        srv.start()
        threading.Event().wait(0.1)
        yield srv
        srv.stop()


def server_url(srv: FileServer) -> str:
    host, port = srv._server.server_address  # pyright: ignore
    return f"http://{host}:{port}"


# -------------------------
# OPTIONS request
# -------------------------
def test_options(server):
    url = server_url(server)
    resp = requests.options(url)
    assert resp.status_code == 200
    assert resp.headers["Access-Control-Allow-Origin"] == "*"
    assert "GET" in resp.headers["Access-Control-Allow-Methods"]


# -------------------------
# File upload with overwrite
# -------------------------
def test_file_upload_overwrite(server):
    url = server_url(server)
    upload_url = f"{url}/?filename={quote('test.txt')}&overwrite=true"
    files = {"file": ("ignored_name", b"hello world")}
    resp = requests.post(upload_url, files=files)
    assert resp.status_code == 200
    assert resp.content == b"Upload successful"

    saved_file = server.files_dir / "test.txt"
    assert saved_file.exists()
    assert saved_file.read_bytes() == b"hello world"

    # Overwrite test
    files = {"file": ("ignored_name", b"new content")}
    resp = requests.post(upload_url, files=files)
    assert resp.status_code == 200
    assert saved_file.read_bytes() == b"new content"


# -------------------------
# Upload without overwrite when file exists
# -------------------------
def test_file_upload_no_overwrite_conflict(server):
    upload_url = (
        f"{server_url(server)}/?filename={quote('conflict.txt')}&overwrite=false"
    )
    file_path = server.files_dir / "conflict.txt"
    file_path.write_bytes(b"existing")

    files = {"file": ("ignored_name", b"new content")}
    resp = requests.post(upload_url, files=files)
    assert resp.status_code == 409
    assert file_path.read_bytes() == b"existing"


# -------------------------
# Upload missing filename
# -------------------------
def test_file_upload_missing_filename(server):
    url = server_url(server)
    files = {"file": ("ignored_name", b"hello")}
    resp = requests.post(url, files=files)
    assert resp.status_code == 400
    assert b"Missing filename" in resp.content


# -------------------------
# File download
# -------------------------
def test_file_download(server):
    test_file = server.files_dir / "download.txt"
    test_file.write_bytes(b"download content")

    url = server_url(server) + "/download.txt"
    resp = requests.get(url)
    assert resp.status_code == 200
    assert resp.content == b"download content"


# -------------------------
# POST non-multipart
# -------------------------
def test_post_non_multipart(server):
    url = server_url(server) + "/?filename=test.txt"
    resp = requests.post(url, data={"foo": "bar"})
    assert resp.status_code == 400
    assert b"Invalid multipart upload" in resp.content


# -------------------------
# ZIP extraction with replace
# -------------------------
def test_zip_extract_replace(server):
    zip_bytes = io.BytesIO()
    with zipfile.ZipFile(zip_bytes, "w") as zf:
        zf.writestr("file1.txt", b"hello")
        zf.writestr("dir/file2.txt", b"world")
    zip_bytes.seek(0)

    url = server_url(server) + "/extract?target=config&replace=true"
    files = {"file": ("ignored.zip", zip_bytes.read())}
    resp = requests.post(url, files=files)
    assert resp.status_code == 200
    assert resp.content == b"ZIP extracted"

    assert (server.files_dir / "config" / "file1.txt").read_bytes() == b"hello"
    assert (server.files_dir / "config" / "dir" / "file2.txt").read_bytes() == b"world"


# -------------------------
# ZIP extraction without target
# -------------------------
def test_zip_extract_missing_target(server):
    zip_bytes = io.BytesIO()
    with zipfile.ZipFile(zip_bytes, "w") as zf:
        zf.writestr("file1.txt", b"hello")
    zip_bytes.seek(0)

    url = server_url(server) + "/extract?replace=true"
    files = {"file": ("ignored.zip", zip_bytes.read())}
    resp = requests.post(url, files=files)
    assert resp.status_code == 400
    assert b"Missing target" in resp.content


# -------------------------
# ZIP extraction without replace when target exists
# -------------------------
def test_zip_extract_no_replace_conflict(server):
    target_dir = server.files_dir / "config"
    target_dir.mkdir()
    (target_dir / "existing.txt").write_bytes(b"data")

    zip_bytes = io.BytesIO()
    with zipfile.ZipFile(zip_bytes, "w") as zf:
        zf.writestr("file1.txt", b"hello")
    zip_bytes.seek(0)

    url = server_url(server) + "/extract?target=config&replace=false"
    files = {"file": ("ignored.zip", zip_bytes.read())}
    resp = requests.post(url, files=files)
    assert resp.status_code == 409


# -------------------------
# Path traversal protection
# -------------------------
def test_upload_path_traversal(server):
    url = server_url(server) + f"/?filename={quote('../outside.txt')}&overwrite=true"
    files = {"file": ("ignored_name", b"hello")}
    resp = requests.post(url, files=files)
    assert resp.status_code == 403


def test_zip_path_traversal(server):
    zip_bytes = io.BytesIO()
    with zipfile.ZipFile(zip_bytes, "w") as zf:
        zf.writestr("../../evil.txt", b"malicious")
    zip_bytes.seek(0)

    url = server_url(server) + "/extract?target=config&replace=true"
    files = {"file": ("ignored.zip", zip_bytes.read())}
    resp = requests.post(url, files=files)
    assert resp.status_code == 400


# -------------------------
# PUT atomic write
# -------------------------
def test_put_atomic_write(server):
    url = server_url(server) + "/atomic.txt"
    resp = requests.put(url, data=b"hello put")
    assert resp.status_code == 200
    saved_file = server.files_dir / "atomic.txt"
    assert saved_file.exists()
    assert saved_file.read_bytes() == b"hello put"

    # Overwrite
    resp = requests.put(url, data=b"new content")
    assert resp.status_code == 200
    assert saved_file.read_bytes() == b"new content"
