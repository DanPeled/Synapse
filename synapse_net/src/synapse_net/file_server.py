# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import http.server
import socketserver
import threading
from pathlib import Path
from typing import Optional


# -------------------------
# HTTP Handler
# -------------------------
class FileServerHandler(http.server.SimpleHTTPRequestHandler):
    """Custom HTTP handler to support file upload and download."""

    files_dir: Path

    def __init__(self, *args, directory: Optional[Path] = None, **kwargs):
        if directory is None:
            raise ValueError("directory must be provided")
        super().__init__(*args, directory=str(directory), **kwargs)
        self.files_dir: Path = directory

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(200, "OK")
        self.end_headers()

    # -------------------------
    # Handle POST (Upload)
    # -------------------------
    def do_POST(self) -> None:
        """Handle file upload via multipart/form-data."""
        content_length: int = int(self.headers.get("Content-Length", 0))
        content_type: str = self.headers.get("Content-Type", "")

        if "multipart/form-data" not in content_type:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Bad request: not multipart/form-data")
            return

        boundary: bytes = content_type.split("boundary=")[-1].encode()
        body: bytes = self.rfile.read(content_length)
        parts: list[bytes] = body.split(boundary)

        uploaded: bool = False
        for part in parts:
            if b'filename="' in part:
                header, file_data = part.split(b"\r\n\r\n", 1)
                file_data = file_data.rstrip(b"\r\n--")
                filename_bytes: bytes = header.split(b'filename="')[1].split(b'"')[0]
                filename: str = filename_bytes.decode(errors="ignore")
                filepath: Path = self.files_dir / filename
                with open(filepath, "wb") as f:
                    f.write(file_data)
                uploaded = True
                break

        if uploaded:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Upload successful")
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"No file found in request")


# -------------------------
# Server Wrapper
# -------------------------
class FileServer:
    """Encapsulates HTTP server in a background thread with configurable files directory."""

    def __init__(self, files_dir: Path, host: str = "0.0.0.0", port: int = 8080):
        self.files_dir: Path = files_dir.resolve()
        self.files_dir.mkdir(parents=True, exist_ok=True)

        self.host: str = host
        self.port: int = port
        self._thread: Optional[threading.Thread] = None
        self._server: Optional[socketserver.TCPServer] = None

    def start(self) -> None:
        """Start the HTTP server in a background daemon thread."""
        files_dir = self.files_dir

        class CustomHandler(FileServerHandler):
            def __init__(self, *args, **kwargs):
                self.files_dir = files_dir
                super().__init__(*args, directory=files_dir, **kwargs)

        class ReusableTCPServer(socketserver.TCPServer):
            allow_reuse_address = True

        self._server = ReusableTCPServer((self.host, self.port), CustomHandler)
        print(
            f"Serving files from '{self.files_dir}' at http://{self.host}:{self.port}/"
        )

        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the HTTP server."""
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            print("Server stopped.")
        if self._thread:
            self._thread.join()
