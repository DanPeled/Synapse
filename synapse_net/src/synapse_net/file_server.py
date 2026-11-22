# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import http.server
import json
import shutil
import socketserver
import tempfile
import threading
import zipfile
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, unquote, urlparse

from synapse.log import info

PREVIEW_MAX_BYTES = 256 * 1024
_TEXT_SAMPLE_BYTES = 8192


class ReusableThreadingTCPServer(socketserver.ThreadingTCPServer):
    """TCP server that handles file requests concurrently and restarts cleanly."""

    allow_reuse_address = True
    daemon_threads = True
    # Handler threads are daemons, so shutdown should not wait for slow clients.
    block_on_close = False


def _decode_text_preview(data: bytes, truncated: bool) -> Optional[str]:
    """Return the file content as text when it looks like a text file."""
    sample = data[:_TEXT_SAMPLE_BYTES]
    if b"\x00" in sample:
        return None

    text: Optional[str] = None
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        if truncated:
            # A multi-byte character may be split at the read boundary.
            for cut in range(1, 4):
                try:
                    text = data[:-cut].decode("utf-8-sig")
                    break
                except UnicodeDecodeError:
                    continue

    if text is None:
        return None

    controlChars = sum(
        1 for char in text if ord(char) < 32 and char not in "\n\r\t\f\b"
    )
    if text and controlChars / len(text) > 0.1:
        return None

    return text


class FileServerHandler(http.server.SimpleHTTPRequestHandler):
    """
    HTTP file server with safe upload, replace, and ZIP extraction support.
    """

    def __init__(self, *args, directory: Optional[Path] = None, **kwargs):
        if directory is None:
            raise ValueError("directory must be provided")

        self.files_dir = directory.resolve()
        super().__init__(*args, directory=str(self.files_dir), **kwargs)

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(200)
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/list":
            self._handle_list(parsed)
        elif parsed.path == "/read":
            self._handle_read(parsed)
        else:
            super().do_GET()

    def _send_json(self, data: Any, status: int = 200) -> None:
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_list(self, parsed) -> None:
        params = parse_qs(parsed.query)
        requested = params.get("path", [""])[0]

        target = self._resolve_safe_path(requested)
        if target is None:
            self.send_error(403, "Invalid path")
            return

        if not target.exists():
            self.send_error(404, "Path does not exist")
            return
        if not target.is_dir():
            self.send_error(400, "Path is not a directory")
            return

        entries = []
        try:
            children = sorted(
                target.iterdir(),
                key=lambda child: (not child.is_dir(), child.name.lower()),
            )
            for child in children:
                if child.is_symlink():
                    continue
                try:
                    isDir = child.is_dir()
                    size = 0 if isDir else child.stat().st_size
                except OSError:
                    continue
                entries.append(
                    {
                        "name": child.name,
                        "path": child.relative_to(self.files_dir).as_posix(),
                        "is_dir": isDir,
                        "size": size,
                    }
                )
        except OSError as e:
            self.send_error(500, f"Unable to list directory: {e}")
            return

        relativePath = (
            "" if target == self.files_dir else target.relative_to(self.files_dir)
        )
        self._send_json(
            {
                "path": relativePath.as_posix() if relativePath else "",
                "entries": entries,
            }
        )

    def _handle_read(self, parsed) -> None:
        params = parse_qs(parsed.query)
        requested = params.get("path", [""])[0]

        if not requested:
            self.send_error(400, "Missing path")
            return

        target = self._resolve_safe_path(requested)
        if target is None:
            self.send_error(403, "Invalid path")
            return

        if not target.exists():
            self.send_error(404, "Path does not exist")
            return
        if not target.is_file():
            self.send_error(400, "Path is not a file")
            return

        try:
            size = target.stat().st_size
            with target.open("rb") as file:
                data = file.read(PREVIEW_MAX_BYTES + 1)
        except OSError as e:
            self.send_error(500, f"Unable to read file: {e}")
            return

        truncated = len(data) > PREVIEW_MAX_BYTES
        data = data[:PREVIEW_MAX_BYTES]
        content = _decode_text_preview(data, truncated)

        self._send_json(
            {
                "path": target.relative_to(self.files_dir).as_posix(),
                "name": target.name,
                "size": size,
                "is_text": content is not None,
                "content": content,
                "truncated": truncated,
                "max_bytes": PREVIEW_MAX_BYTES,
            }
        )

    def _resolve_safe_path(self, path: str) -> Optional[Path]:
        resolved = (self.files_dir / path.lstrip("/")).resolve()
        if not resolved.is_relative_to(self.files_dir):
            return None
        return resolved

    def _atomic_write(self, target: Path, data: bytes) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(target)

    def _parse_multipart_file(self) -> Optional[bytes]:
        content_length = int(self.headers.get("Content-Length", 0))
        content_type = self.headers.get("Content-Type", "")

        if "multipart/form-data" not in content_type:
            return None

        boundary = content_type.split("boundary=")[-1].encode()
        body = self.rfile.read(content_length)

        for part in body.split(boundary):
            if b'filename="' in part:
                _, data = part.split(b"\r\n\r\n", 1)
                return data.rstrip(b"\r\n--")

        return None

    def do_PUT(self) -> None:
        parsed = urlparse(self.path)
        target = self._resolve_safe_path(unquote(parsed.path))
        if target is None:
            self.send_error(403)
            return

        length = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(length)

        self._atomic_write(target, data)

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"File written")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path == "/extract":
            self._handle_zip_extract(parsed)
        else:
            self._handle_file_upload(parsed)

    def _handle_file_upload(self, parsed) -> None:
        params = parse_qs(parsed.query)
        overwrite = params.get("overwrite", ["false"])[0].lower() == "true"

        file_data = self._parse_multipart_file()
        if file_data is None:
            self.send_error(400, "Invalid multipart upload")
            return

        filename = params.get("filename", [None])[0]
        if not filename:
            self.send_error(400, "Missing filename")
            return

        target = self._resolve_safe_path(filename)
        if target is None:
            self.send_error(403)
            return

        if target.exists() and not overwrite:
            self.send_error(409, "File exists")
            return

        self._atomic_write(target, file_data)

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Upload successful")

    def _handle_zip_extract(self, parsed) -> None:
        params = parse_qs(parsed.query)
        target_name = params.get("target", [None])[0]
        replace = params.get("replace", ["false"])[0].lower() == "true"

        if not target_name:
            self.send_error(400, "Missing target")
            return

        zip_data = self._parse_multipart_file()
        if zip_data is None:
            self.send_error(400, "Invalid ZIP upload")
            return

        target_dir = self._resolve_safe_path(target_name)
        if target_dir is None:
            self.send_error(403)
            return

        try:
            self._extract_zip_atomic(zip_data, target_dir, replace)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ZIP extracted")

        except FileExistsError:
            self.send_error(409, "Target exists")
        except ValueError as e:
            self.send_error(400, str(e))

    def _extract_zip_atomic(
        self, zip_bytes: bytes, target_dir: Path, replace: bool
    ) -> None:
        if target_dir.exists() and not replace:
            raise FileExistsError

        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)

            zip_path = tmp / "upload.zip"
            zip_path.write_bytes(zip_bytes)

            extract_root = tmp / "extract"
            extract_root.mkdir()

            with zipfile.ZipFile(zip_path) as z:
                for name in z.namelist():
                    resolved = (extract_root / name).resolve()
                    if not resolved.is_relative_to(extract_root):
                        raise ValueError("Zip path traversal detected")

                z.extractall(extract_root)

            if target_dir.exists():
                shutil.rmtree(target_dir)

            shutil.move(str(extract_root), str(target_dir))


class FileServer:
    """
    Background-threaded HTTP file server.
    """

    def __init__(
        self,
        files_dir: Path,
        host: str = "0.0.0.0",
        port: int = 8080,
    ):
        self.files_dir = files_dir.resolve()
        self.files_dir.mkdir(parents=True, exist_ok=True)

        self.host = host
        self.port = port
        self._server: Optional[ReusableThreadingTCPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        files_dir = self.files_dir

        class Handler(FileServerHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=files_dir, **kwargs)

        self._server = ReusableThreadingTCPServer((self.host, self.port), Handler)

        info(f"File server running at http://{self.host}:{self.port}/")

        self._thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
        if self._thread:
            self._thread.join()
